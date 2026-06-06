import json
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class StoredChunk:
    chunk_id: str
    document_id: str
    content: str
    source: str
    chunk_order: int
    metadata_json: str = "{}"


class MetadataRepository:
    def __init__(
        self,
        mysql_client: object,
        retry_attempts: int = 3,
        retry_backoff_seconds: float = 0.2,
    ) -> None:
        self.mysql_client = mysql_client
        self.retry_attempts = max(1, retry_attempts)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)
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

    def _fetchall(self, sql: str, params: tuple = ()) -> list[tuple[Any, ...]]:
        def _inner() -> list[tuple[Any, ...]]:
            with self.mysql_client.cursor() as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())

        return self._run_with_retry(_inner)

    def _ensure_schema(self) -> None:
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_id VARCHAR(128) PRIMARY KEY,
                source VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id VARCHAR(191) PRIMARY KEY,
                document_id VARCHAR(128) NOT NULL,
                content LONGTEXT NOT NULL,
                source VARCHAR(255) NOT NULL,
                chunk_order INT NOT NULL,
                metadata_json LONGTEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_chunks_doc (document_id),
                CONSTRAINT fk_chunks_documents
                    FOREIGN KEY (document_id) REFERENCES documents(document_id)
                    ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )

    def upsert_document(self, document_id: str, source: str) -> None:
        self._execute(
            """
            INSERT INTO documents(document_id, source)
            VALUES(%s, %s)
            ON DUPLICATE KEY UPDATE source = VALUES(source)
            """,
            (document_id, source),
        )

    def replace_chunks(
        self,
        document_id: str,
        source: str,
        chunks: list[tuple[str, dict]],
    ) -> int:
        self.upsert_document(document_id=document_id, source=source)
        self._execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
        values = [
            (
                f"{document_id}-chunk-{idx}",
                document_id,
                content,
                source,
                idx,
                json.dumps(metadata, ensure_ascii=False),
            )
            for idx, (content, metadata) in enumerate(chunks)
        ]
        if values:
            def _inner() -> None:
                with self.mysql_client.cursor() as cursor:
                    cursor.executemany(
                        """
                        INSERT INTO chunks(
                            chunk_id, document_id, content, source, chunk_order, metadata_json
                        )
                        VALUES(%s, %s, %s, %s, %s, %s)
                        """,
                        values,
                    )
                self.mysql_client.commit()

            self._run_with_retry(_inner)
        return len(values)

    def list_chunks(self) -> list[StoredChunk]:
        rows = self._fetchall(
            """
            SELECT chunk_id, document_id, content, source, chunk_order, metadata_json
            FROM chunks
            ORDER BY created_at ASC, chunk_order ASC
            """
        )
        return [
            StoredChunk(
                chunk_id=r[0],
                document_id=r[1],
                content=r[2],
                source=r[3],
                chunk_order=int(r[4]),
                metadata_json=r[5] or "{}",
            )
            for r in rows
        ]

    def list_chunks_by_doc(self, document_id: str) -> list[StoredChunk]:
        rows = self._fetchall(
            """
            SELECT chunk_id, document_id, content, source, chunk_order, metadata_json
            FROM chunks
            WHERE document_id = %s
            ORDER BY chunk_order ASC
            """,
            (document_id,),
        )
        return [
            StoredChunk(
                chunk_id=r[0],
                document_id=r[1],
                content=r[2],
                source=r[3],
                chunk_order=int(r[4]),
                metadata_json=r[5] or "{}",
            )
            for r in rows
        ]

    def delete_document(self, document_id: str) -> bool:
        def _inner() -> bool:
            with self.mysql_client.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM documents WHERE document_id = %s",
                    (document_id,),
                )
                affected = int(getattr(cursor, "rowcount", 0))
            self.mysql_client.commit()
            return affected > 0

        return bool(self._run_with_retry(_inner))
