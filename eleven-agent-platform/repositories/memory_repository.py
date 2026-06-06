from dataclasses import dataclass
import time
from collections.abc import Callable


@dataclass
class MemoryRepository:
    mysql_client: object
    redis_client: object
    session_ttl_seconds: int
    session_max_messages: int
    retry_attempts: int = 3
    retry_backoff_seconds: float = 0.2
    op_alert_threshold_ms: int = 200
    failure_alert_threshold: int = 3
    monitor_enabled: bool = True

    def __post_init__(self) -> None:
        self.retry_attempts = max(1, int(self.retry_attempts))
        self.retry_backoff_seconds = max(0.0, float(self.retry_backoff_seconds))
        self.op_alert_threshold_ms = max(1, int(self.op_alert_threshold_ms))
        self.failure_alert_threshold = max(1, int(self.failure_alert_threshold))
        self._metrics: dict[str, dict[str, float | int]] = {
            "upsert_preference": {"calls": 0, "failures": 0, "slow_calls": 0, "avg_ms": 0.0},
            "delete_preference": {"calls": 0, "failures": 0, "slow_calls": 0, "avg_ms": 0.0},
            "rollback_preference": {"calls": 0, "failures": 0, "slow_calls": 0, "avg_ms": 0.0},
            "get_preferences": {"calls": 0, "failures": 0, "slow_calls": 0, "avg_ms": 0.0},
            "get_preference_history": {"calls": 0, "failures": 0, "slow_calls": 0, "avg_ms": 0.0},
            "upsert_session_summary": {"calls": 0, "failures": 0, "slow_calls": 0, "avg_ms": 0.0},
            "list_session_summaries": {"calls": 0, "failures": 0, "slow_calls": 0, "avg_ms": 0.0},
            "get_session_summary_checkpoint": {"calls": 0, "failures": 0, "slow_calls": 0, "avg_ms": 0.0},
            "append_session_message": {"calls": 0, "failures": 0, "slow_calls": 0, "avg_ms": 0.0},
            "get_session_messages": {"calls": 0, "failures": 0, "slow_calls": 0, "avg_ms": 0.0},
        }

    def _alert(self, message: str) -> None:
        if self.monitor_enabled:
            print(f"[memory-alert] {message}")

    def _record_metric(self, op_name: str, duration_ms: float, failed: bool) -> None:
        bucket = self._metrics[op_name]
        calls = int(bucket["calls"]) + 1
        prev_avg = float(bucket["avg_ms"])
        bucket["calls"] = calls
        bucket["avg_ms"] = ((prev_avg * (calls - 1)) + duration_ms) / calls

        if duration_ms > self.op_alert_threshold_ms:
            bucket["slow_calls"] = int(bucket["slow_calls"]) + 1
            self._alert(
                f"{op_name} slow call: {round(duration_ms, 2)}ms "
                f"(threshold={self.op_alert_threshold_ms}ms)"
            )

        if failed:
            failures = int(bucket["failures"]) + 1
            bucket["failures"] = failures
            if failures >= self.failure_alert_threshold:
                self._alert(
                    f"{op_name} failures reached {failures} "
                    f"(threshold={self.failure_alert_threshold})"
                )

    def _run_with_retry(self, op_name: str, fn: Callable[[], object]):
        last_exc: Exception | None = None
        for attempt in range(self.retry_attempts):
            start = time.perf_counter()
            try:
                result = fn()
                self._record_metric(
                    op_name,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    failed=False,
                )
                return result
            except Exception as exc:  # noqa: BLE001
                self._record_metric(
                    op_name,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    failed=True,
                )
                last_exc = exc
                if attempt + 1 >= self.retry_attempts:
                    break
                time.sleep(self.retry_backoff_seconds * (attempt + 1))

        assert last_exc is not None
        raise last_exc

    def _execute(self, op_name: str, sql: str, params: tuple) -> None:
        def _inner() -> None:
            with self.mysql_client.cursor() as cursor:
                cursor.execute(sql, params)
            self.mysql_client.commit()

        self._run_with_retry(op_name, _inner)

    @staticmethod
    def _current_value(row) -> str | None:
        if row is None:
            return None
        if len(row) < 2:
            return row[0]
        return row[0]

    @staticmethod
    def _is_deleted(row) -> bool:
        return bool(row[1]) if row and len(row) > 1 else False

    @staticmethod
    def _write_version_row(
        cursor,
        user_id: str,
        key: str,
        change_type: str,
        old_value: str | None,
        new_value: str | None,
        changed_by: str,
        change_reason: str,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO user_preference_versions (
                user_id,
                pref_key,
                change_type,
                old_value,
                new_value,
                changed_by,
                change_reason
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, key, change_type, old_value, new_value, changed_by, change_reason),
        )

    @staticmethod
    def _fetch_preference_row(cursor, user_id: str, key: str):
        cursor.execute(
            """
            SELECT pref_value, is_deleted
            FROM user_preferences
            WHERE user_id = %s AND pref_key = %s
            LIMIT 1
            """,
            (user_id, key),
        )
        return cursor.fetchone()

    def upsert_preference(
        self,
        user_id: str,
        key: str,
        value: str,
        changed_by: str = "api",
        change_reason: str = "upsert",
    ) -> None:
        def _inner() -> None:
            with self.mysql_client.cursor() as cursor:
                row = self._fetch_preference_row(cursor, user_id, key)
                old_value = self._current_value(row)
                was_deleted = self._is_deleted(row)

                cursor.execute(
                    """
                    INSERT INTO user_preferences (user_id, pref_key, pref_value, is_deleted, deleted_at)
                    VALUES (%s, %s, %s, 0, NULL)
                    ON DUPLICATE KEY UPDATE
                        pref_value = VALUES(pref_value),
                        is_deleted = 0,
                        deleted_at = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, key, value),
                )

                change_type = "create" if row is None else ("restore" if was_deleted else "update")
                self._write_version_row(
                    cursor,
                    user_id=user_id,
                    key=key,
                    change_type=change_type,
                    old_value=old_value,
                    new_value=value,
                    changed_by=changed_by,
                    change_reason=change_reason,
                )
            self.mysql_client.commit()

        self._run_with_retry("upsert_preference", _inner)

    def get_preferences(self, user_id: str) -> dict[str, str]:
        def _inner():
            with self.mysql_client.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT pref_key, pref_value
                    FROM user_preferences
                    WHERE user_id = %s
                      AND is_deleted = 0
                    ORDER BY updated_at ASC, id ASC
                    """,
                    (user_id,),
                )
                return cursor.fetchall()

        rows = self._run_with_retry("get_preferences", _inner)
        return {row[0]: row[1] for row in rows}

    def delete_preference(
        self,
        user_id: str,
        key: str,
        changed_by: str = "api",
        change_reason: str = "delete",
    ) -> bool:
        def _inner() -> bool:
            with self.mysql_client.cursor() as cursor:
                row = self._fetch_preference_row(cursor, user_id, key)
                if row is None or self._is_deleted(row):
                    return False

                old_value = self._current_value(row)
                cursor.execute(
                    """
                    UPDATE user_preferences
                    SET is_deleted = 1,
                        deleted_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND pref_key = %s AND is_deleted = 0
                    """,
                    (user_id, key),
                )
                self._write_version_row(
                    cursor,
                    user_id=user_id,
                    key=key,
                    change_type="delete",
                    old_value=old_value,
                    new_value=None,
                    changed_by=changed_by,
                    change_reason=change_reason,
                )
            self.mysql_client.commit()
            return True

        return bool(self._run_with_retry("delete_preference", _inner))

    def rollback_preference(
        self,
        user_id: str,
        key: str,
        target_version: int | None = None,
        changed_by: str = "api",
        change_reason: str = "rollback",
    ) -> bool:
        def _inner() -> bool:
            with self.mysql_client.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        user_id,
                        pref_key,
                        version,
                        change_type,
                        old_value,
                        new_value,
                        changed_by,
                        change_reason,
                        changed_at
                    FROM user_preference_versions
                    WHERE user_id = %s AND pref_key = %s
                    ORDER BY version ASC
                    """,
                    (user_id, key),
                )
                history = list(cursor.fetchall())
                if not history:
                    return False

                target_row = None
                if target_version is None:
                    target_row = history[-1]
                else:
                    for row in history:
                        if int(row[2]) == int(target_version):
                            target_row = row
                            break
                if target_row is None:
                    return False

                current_row = self._fetch_preference_row(cursor, user_id, key)
                current_value = self._current_value(current_row)

                if target_version is None:
                    if target_row[3] == "delete":
                        restore_value = target_row[4]
                    else:
                        restore_value = None
                        for row in reversed(history[:-1]):
                            if row[5] is not None:
                                restore_value = row[5]
                                break
                else:
                    restore_value = target_row[5] if target_row[5] is not None else target_row[4]

                if target_version is None and restore_value is None:
                    if current_row is None or self._is_deleted(current_row):
                        return False
                    cursor.execute(
                        """
                        UPDATE user_preferences
                        SET is_deleted = 1,
                            deleted_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s AND pref_key = %s AND is_deleted = 0
                        """,
                        (user_id, key),
                    )
                    self._write_version_row(
                        cursor,
                        user_id=user_id,
                        key=key,
                        change_type="rollback",
                        old_value=current_value,
                        new_value=None,
                        changed_by=changed_by,
                        change_reason=change_reason,
                    )
                    self.mysql_client.commit()
                    return True

                if restore_value is None:
                    return False

                cursor.execute(
                    """
                    INSERT INTO user_preferences (user_id, pref_key, pref_value, is_deleted, deleted_at)
                    VALUES (%s, %s, %s, 0, NULL)
                    ON DUPLICATE KEY UPDATE
                        pref_value = VALUES(pref_value),
                        is_deleted = 0,
                        deleted_at = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, key, restore_value),
                )
                self._write_version_row(
                    cursor,
                    user_id=user_id,
                    key=key,
                    change_type="rollback",
                    old_value=current_value,
                    new_value=restore_value,
                    changed_by=changed_by,
                    change_reason=change_reason,
                )
            self.mysql_client.commit()
            return True

        return bool(self._run_with_retry("rollback_preference", _inner))

    def get_preference_history(
        self,
        user_id: str,
        key: str,
    ) -> list[tuple]:
        def _inner():
            with self.mysql_client.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        user_id,
                        pref_key,
                        version,
                        change_type,
                        old_value,
                        new_value,
                        changed_by,
                        change_reason,
                        changed_at
                    FROM user_preference_versions
                    WHERE user_id = %s AND pref_key = %s
                    ORDER BY version ASC
                    """,
                    (user_id, key),
                )
                return cursor.fetchall()

        return list(self._run_with_retry("get_preference_history", _inner))

    def append_session_message(self, session_id: str, message: str) -> None:
        def _inner() -> None:
            key = f"rag:session:{session_id}:messages"
            pipe = self.redis_client.pipeline()
            pipe.rpush(key, message)
            pipe.ltrim(key, -self.session_max_messages, -1)
            pipe.expire(key, self.session_ttl_seconds)
            pipe.execute()

        self._run_with_retry("append_session_message", _inner)

    def get_session_messages(self, session_id: str) -> list[str]:
        def _inner():
            key = f"rag:session:{session_id}:messages"
            return self.redis_client.lrange(key, 0, -1)

        raw_items = self._run_with_retry("get_session_messages", _inner)
        messages: list[str] = []
        for item in raw_items:
            if isinstance(item, bytes):
                item = item.decode("utf-8")
            messages.append(str(item))
        return messages

    def upsert_session_summary(
        self,
        user_id: str,
        session_id: str,
        summary_text: str,
        last_message_count: int,
    ) -> None:
        def _inner() -> None:
            with self.mysql_client.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO session_summaries (
                        user_id,
                        session_id,
                        summary_text,
                        last_message_count
                    )
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        summary_text = VALUES(summary_text),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, session_id, summary_text, last_message_count),
                )
            self.mysql_client.commit()

        self._run_with_retry("upsert_session_summary", _inner)

    def list_session_summaries(self, user_id: str, limit: int = 3) -> list[tuple]:
        safe_limit = max(1, int(limit))

        def _inner():
            with self.mysql_client.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, session_id, summary_text, last_message_count, updated_at
                    FROM session_summaries
                    WHERE user_id = %s
                    ORDER BY updated_at DESC, id DESC
                    LIMIT %s
                    """,
                    (user_id, safe_limit),
                )
                return cursor.fetchall()

        return list(self._run_with_retry("list_session_summaries", _inner))

    def get_session_summary_checkpoint(self, session_id: str) -> int:
        def _inner():
            with self.mysql_client.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(MAX(last_message_count), 0)
                    FROM session_summaries
                    WHERE session_id = %s
                    """,
                    (session_id,),
                )
                return cursor.fetchone()

        row = self._run_with_retry("get_session_summary_checkpoint", _inner)
        if not row:
            return 0
        return int(row[0] or 0)

    def get_metrics_snapshot(self) -> dict[str, dict[str, float | int]]:
        snapshot: dict[str, dict[str, float | int]] = {}
        for op_name, bucket in self._metrics.items():
            snapshot[op_name] = {
                "calls": int(bucket["calls"]),
                "failures": int(bucket["failures"]),
                "slow_calls": int(bucket["slow_calls"]),
                "avg_ms": round(float(bucket["avg_ms"]), 2),
            }
        return snapshot
