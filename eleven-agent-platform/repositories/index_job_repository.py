import json
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class StoredIndexJob:
    job_id: str
    job_type: str
    entity_id: str
    action: str
    status: str
    payload: dict[str, Any]
    attempts: int
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class IndexJobRepository:
    def __init__(
        self,
        mysql_client: object,
        retry_attempts: int = 3,
        retry_backoff_seconds: float = 0.2,
    ) -> None:
        self.mysql_client = mysql_client
        self.retry_attempts = max(1, int(retry_attempts))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self._ensure_schema()

    def _run_with_retry(self, fn: Callable[[], Any]) -> Any:
        last_exc: Exception | None = None
        for attempt in range(self.retry_attempts):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt + 1 >= self.retry_attempts:
                    break
                time.sleep(self.retry_backoff_seconds * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    def _execute(self, sql: str, params: tuple = ()) -> None:
        def _inner() -> None:
            with self.mysql_client.cursor() as cursor:
                cursor.execute(sql, params)
            self.mysql_client.commit()

        self._run_with_retry(_inner)

    def _fetchone(self, sql: str, params: tuple = ()) -> tuple[Any, ...] | None:
        def _inner():
            with self.mysql_client.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone()

        return self._run_with_retry(_inner)

    def _fetchall(self, sql: str, params: tuple = ()) -> list[tuple[Any, ...]]:
        def _inner():
            with self.mysql_client.cursor() as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())

        return self._run_with_retry(_inner)

    def _ensure_schema(self) -> None:
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS index_jobs (
                job_id VARCHAR(128) PRIMARY KEY,
                job_type VARCHAR(32) NOT NULL,
                entity_id VARCHAR(128) NOT NULL,
                action_name VARCHAR(32) NOT NULL,
                status VARCHAR(32) NOT NULL,
                payload_json LONGTEXT NOT NULL,
                attempts INT NOT NULL DEFAULT 0,
                error_message TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                started_at TIMESTAMP NULL DEFAULT NULL,
                completed_at TIMESTAMP NULL DEFAULT NULL,
                KEY idx_index_jobs_status_created_at (status, created_at),
                KEY idx_index_jobs_entity (job_type, entity_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )

    @staticmethod
    def _map_row(row: tuple[Any, ...]) -> StoredIndexJob:
        return StoredIndexJob(
            job_id=str(row[0]),
            job_type=str(row[1]),
            entity_id=str(row[2]),
            action=str(row[3]),
            status=str(row[4]),
            payload=json.loads(row[5] or "{}"),
            attempts=int(row[6]),
            error_message=None if row[7] is None else str(row[7]),
            created_at=None if row[8] is None else str(row[8]),
            updated_at=None if row[9] is None else str(row[9]),
            started_at=None if row[10] is None else str(row[10]),
            completed_at=None if row[11] is None else str(row[11]),
        )

    def create_job(
        self,
        job_id: str,
        job_type: str,
        entity_id: str,
        action: str,
        payload: dict[str, Any],
    ) -> StoredIndexJob:
        self._execute(
            """
            INSERT INTO index_jobs(
                job_id, job_type, entity_id, action_name, status, payload_json, attempts
            )
            VALUES(%s, %s, %s, %s, 'pending', %s, 0)
            """,
            (job_id, job_type, entity_id, action, json.dumps(payload, ensure_ascii=False)),
        )
        job = self.get_job(job_id)
        assert job is not None
        return job

    def get_job(self, job_id: str) -> StoredIndexJob | None:
        row = self._fetchone(
            """
            SELECT job_id, job_type, entity_id, action_name, status, payload_json, attempts,
                   error_message, created_at, updated_at, started_at, completed_at
            FROM index_jobs
            WHERE job_id = %s
            """,
            (job_id,),
        )
        return None if row is None else self._map_row(row)

    def list_jobs_by_status(
        self,
        statuses: list[str],
        limit: int,
    ) -> list[StoredIndexJob]:
        cleaned = [status.strip() for status in statuses if status and status.strip()]
        if not cleaned:
            return []
        placeholders = ", ".join(["%s"] * len(cleaned))
        rows = self._fetchall(
            f"""
            SELECT job_id, job_type, entity_id, action_name, status, payload_json, attempts,
                   error_message, created_at, updated_at, started_at, completed_at
            FROM index_jobs
            WHERE status IN ({placeholders})
            ORDER BY created_at ASC
            LIMIT %s
            """,
            tuple(cleaned + [max(1, limit)]),
        )
        return [self._map_row(row) for row in rows]

    def mark_processing(self, job_id: str) -> StoredIndexJob:
        self._execute(
            """
            UPDATE index_jobs
            SET status = 'processing',
                attempts = attempts + 1,
                started_at = CURRENT_TIMESTAMP,
                error_message = NULL
            WHERE job_id = %s
            """,
            (job_id,),
        )
        job = self.get_job(job_id)
        assert job is not None
        return job

    def mark_ready(self, job_id: str) -> StoredIndexJob:
        self._execute(
            """
            UPDATE index_jobs
            SET status = 'ready',
                completed_at = CURRENT_TIMESTAMP,
                error_message = NULL
            WHERE job_id = %s
            """,
            (job_id,),
        )
        job = self.get_job(job_id)
        assert job is not None
        return job

    def mark_failed(self, job_id: str, error_message: str) -> StoredIndexJob:
        self._execute(
            """
            UPDATE index_jobs
            SET status = 'failed',
                error_message = %s,
                completed_at = CURRENT_TIMESTAMP
            WHERE job_id = %s
            """,
            (error_message[:1000], job_id),
        )
        job = self.get_job(job_id)
        assert job is not None
        return job

    def summarize_statuses(self) -> dict[str, int]:
        rows = self._fetchall(
            """
            SELECT status, COUNT(*)
            FROM index_jobs
            GROUP BY status
            """
        )
        return {str(status): int(count) for status, count in rows}
