from dataclasses import dataclass
import time
from collections.abc import Callable

from core.app_logging import get_logger


logger = get_logger(__name__)


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
            "get_preferences": {"calls": 0, "failures": 0, "slow_calls": 0, "avg_ms": 0.0},
            "append_session_message": {"calls": 0, "failures": 0, "slow_calls": 0, "avg_ms": 0.0},
            "get_session_messages": {"calls": 0, "failures": 0, "slow_calls": 0, "avg_ms": 0.0},
        }

    def _alert(self, message: str) -> None:
        if self.monitor_enabled:
            logger.warning(
                message,
                extra={"event": "memory_alert", "stage": "memory_repository"},
            )

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

    def _execute(self, sql: str, params: tuple) -> None:
        def _inner() -> None:
            with self.mysql_client.cursor() as cursor:
                cursor.execute(sql, params)
            self.mysql_client.commit()

        self._run_with_retry("upsert_preference", _inner)

    def upsert_preference(self, user_id: str, key: str, value: str) -> None:
        self._execute(
            """
            INSERT INTO user_preferences (user_id, pref_key, pref_value)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                pref_value = VALUES(pref_value),
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, key, value),
        )

    def get_preferences(self, user_id: str) -> dict[str, str]:
        def _inner():
            with self.mysql_client.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT pref_key, pref_value
                    FROM user_preferences
                    WHERE user_id = %s
                    ORDER BY updated_at ASC, id ASC
                    """,
                    (user_id,),
                )
                return cursor.fetchall()

        rows = self._run_with_retry("get_preferences", _inner)
        return {row[0]: row[1] for row in rows}

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
