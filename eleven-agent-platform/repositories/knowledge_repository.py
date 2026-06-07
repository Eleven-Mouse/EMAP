import json
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class StoredKnowledgeMemory:
    memory_id: str
    scope_id: str
    title: str
    content: str
    source: str
    tags: list[str]
    metadata: dict[str, Any]
    status: str
    version: int
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None


@dataclass
class KnowledgeMemoryVersion:
    memory_id: str
    version: int
    scope_id: str
    title: str
    content: str
    source: str
    tags: list[str]
    metadata: dict[str, Any]
    status: str
    actor_id: str
    change_note: str
    snapshot_at: str | None = None


class KnowledgeRepository:
    def __init__(
        self,
        mysql_client: object,
        retry_attempts: int = 3,
        retry_backoff_seconds: float = 0.2,
    ) -> None:
        self.mysql_client = mysql_client
        self.retry_attempts = max(1, int(retry_attempts))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))

    def _run_with_retry(self, fn):
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

    @staticmethod
    def _encode_tags(tags: list[str]) -> str:
        cleaned = [str(tag).strip() for tag in tags if str(tag).strip()]
        return json.dumps(cleaned, ensure_ascii=False)

    @staticmethod
    def _encode_metadata(metadata: dict[str, Any]) -> str:
        return json.dumps(metadata or {}, ensure_ascii=False)

    @staticmethod
    def _decode_tags(raw: str | None) -> list[str]:
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
        return [str(item) for item in payload]

    @staticmethod
    def _decode_metadata(raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _map_memory_row(self, row: tuple[Any, ...]) -> StoredKnowledgeMemory:
        return StoredKnowledgeMemory(
            memory_id=str(row[0]),
            scope_id=str(row[1]),
            title=str(row[2]),
            content=str(row[3]),
            source=str(row[4]),
            tags=self._decode_tags(row[5]),
            metadata=self._decode_metadata(row[6]),
            status=str(row[7]),
            version=int(row[8]),
            created_at=None if row[9] is None else str(row[9]),
            updated_at=None if row[10] is None else str(row[10]),
            deleted_at=None if row[11] is None else str(row[11]),
        )

    def _map_history_row(self, row: tuple[Any, ...]) -> KnowledgeMemoryVersion:
        return KnowledgeMemoryVersion(
            memory_id=str(row[0]),
            version=int(row[1]),
            scope_id=str(row[2]),
            title=str(row[3]),
            content=str(row[4]),
            source=str(row[5]),
            tags=self._decode_tags(row[6]),
            metadata=self._decode_metadata(row[7]),
            status=str(row[8]),
            actor_id=str(row[9]),
            change_note=str(row[10] or ""),
            snapshot_at=None if row[11] is None else str(row[11]),
        )

    def _snapshot_memory(
        self,
        memory: StoredKnowledgeMemory,
        actor_id: str,
        change_note: str,
    ) -> None:
        self._execute(
            """
            INSERT INTO knowledge_memory_versions(
                memory_id, version, scope_id, title, content, source,
                tags_json, metadata_json, status, actor_id, change_note
            )
            VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                memory.memory_id,
                memory.version,
                memory.scope_id,
                memory.title,
                memory.content,
                memory.source,
                self._encode_tags(memory.tags),
                self._encode_metadata(memory.metadata),
                memory.status,
                actor_id,
                change_note,
            ),
        )

    def _record_event(
        self,
        memory_id: str,
        event_type: str,
        actor_id: str,
        detail: dict[str, Any],
    ) -> None:
        self._execute(
            """
            INSERT INTO knowledge_memory_events(memory_id, event_type, actor_id, detail_json)
            VALUES(%s, %s, %s, %s)
            """,
            (
                memory_id,
                event_type,
                actor_id,
                json.dumps(detail, ensure_ascii=False),
            ),
        )

    def get_memory(
        self,
        memory_id: str,
        include_deleted: bool = True,
    ) -> StoredKnowledgeMemory | None:
        sql = """
            SELECT memory_id, scope_id, title, content, source, tags_json, metadata_json,
                   status, version, created_at, updated_at, deleted_at
            FROM knowledge_memories
            WHERE memory_id = %s
        """
        params: tuple[Any, ...] = (memory_id,)
        if not include_deleted:
            sql += " AND status = 'active'"
        row = self._fetchone(sql, params)
        return None if row is None else self._map_memory_row(row)

    def list_active_memories(
        self,
        scope_prefixes: list[str] | None = None,
    ) -> list[StoredKnowledgeMemory]:
        rows = self._fetchall(
            """
            SELECT memory_id, scope_id, title, content, source, tags_json, metadata_json,
                   status, version, created_at, updated_at, deleted_at
            FROM knowledge_memories
            WHERE status = 'active'
            ORDER BY updated_at DESC, memory_id ASC
            """
        )
        memories = [self._map_memory_row(row) for row in rows]
        if not scope_prefixes:
            return memories
        prefixes = [prefix.strip() for prefix in scope_prefixes if prefix and prefix.strip()]
        if not prefixes:
            return memories
        return [
            memory
            for memory in memories
            if any(memory.scope_id.startswith(prefix) for prefix in prefixes)
        ]

    def create_memory(
        self,
        memory_id: str,
        scope_id: str,
        title: str,
        content: str,
        source: str,
        tags: list[str],
        metadata: dict[str, Any],
        actor_id: str,
        change_note: str = "",
    ) -> StoredKnowledgeMemory:
        existing = self.get_memory(memory_id)
        if existing is not None:
            raise ValueError(f"Knowledge memory already exists: {memory_id}")

        self._execute(
            """
            INSERT INTO knowledge_memories(
                memory_id, scope_id, title, content, source, tags_json, metadata_json,
                status, version, deleted_at
            )
            VALUES(%s, %s, %s, %s, %s, %s, %s, 'active', 1, NULL)
            """,
            (
                memory_id,
                scope_id,
                title,
                content,
                source,
                self._encode_tags(tags),
                self._encode_metadata(metadata),
            ),
        )
        memory = self.get_memory(memory_id)
        assert memory is not None
        self._snapshot_memory(memory, actor_id=actor_id, change_note=change_note)
        self._record_event(
            memory_id=memory_id,
            event_type="created",
            actor_id=actor_id,
            detail={"version": memory.version, "change_note": change_note},
        )
        return memory

    def update_memory(
        self,
        memory_id: str,
        actor_id: str,
        change_note: str = "",
        title: str | None = None,
        content: str | None = None,
        source: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StoredKnowledgeMemory:
        if all(value is None for value in (title, content, source, tags, metadata)):
            raise ValueError("Knowledge memory update requires at least one changed field")
        current = self.get_memory(memory_id)
        if current is None:
            raise KeyError(f"Knowledge memory not found: {memory_id}")
        if current.status != "active":
            raise ValueError(f"Knowledge memory is not editable in status={current.status}")

        updated = StoredKnowledgeMemory(
            memory_id=current.memory_id,
            scope_id=current.scope_id,
            title=title or current.title,
            content=content or current.content,
            source=source or current.source,
            tags=current.tags if tags is None else tags,
            metadata=current.metadata if metadata is None else metadata,
            status="active",
            version=current.version + 1,
            created_at=current.created_at,
            updated_at=current.updated_at,
            deleted_at=None,
        )
        self._execute(
            """
            UPDATE knowledge_memories
            SET title = %s,
                content = %s,
                source = %s,
                tags_json = %s,
                metadata_json = %s,
                status = 'active',
                version = %s,
                deleted_at = NULL
            WHERE memory_id = %s
            """,
            (
                updated.title,
                updated.content,
                updated.source,
                self._encode_tags(updated.tags),
                self._encode_metadata(updated.metadata),
                updated.version,
                memory_id,
            ),
        )
        updated = self.get_memory(memory_id)
        assert updated is not None
        self._snapshot_memory(updated, actor_id=actor_id, change_note=change_note)
        self._record_event(
            memory_id=memory_id,
            event_type="updated",
            actor_id=actor_id,
            detail={"version": updated.version, "change_note": change_note},
        )
        return updated

    def soft_delete_memory(
        self,
        memory_id: str,
        actor_id: str,
        change_note: str = "",
    ) -> StoredKnowledgeMemory:
        current = self.get_memory(memory_id)
        if current is None:
            raise KeyError(f"Knowledge memory not found: {memory_id}")
        if current.status == "deleted":
            raise ValueError(f"Knowledge memory already deleted: {memory_id}")

        next_version = current.version + 1
        self._execute(
            """
            UPDATE knowledge_memories
            SET status = 'deleted',
                version = %s,
                deleted_at = CURRENT_TIMESTAMP
            WHERE memory_id = %s
            """,
            (next_version, memory_id),
        )
        deleted = self.get_memory(memory_id)
        assert deleted is not None
        self._snapshot_memory(deleted, actor_id=actor_id, change_note=change_note)
        self._record_event(
            memory_id=memory_id,
            event_type="deleted",
            actor_id=actor_id,
            detail={"version": deleted.version, "change_note": change_note},
        )
        return deleted

    def restore_memory(
        self,
        memory_id: str,
        actor_id: str,
        change_note: str = "",
    ) -> StoredKnowledgeMemory:
        current = self.get_memory(memory_id)
        if current is None:
            raise KeyError(f"Knowledge memory not found: {memory_id}")
        if current.status != "deleted":
            raise ValueError(f"Knowledge memory is not deleted: {memory_id}")

        next_version = current.version + 1
        self._execute(
            """
            UPDATE knowledge_memories
            SET status = 'active',
                version = %s,
                deleted_at = NULL
            WHERE memory_id = %s
            """,
            (next_version, memory_id),
        )
        restored = self.get_memory(memory_id)
        assert restored is not None
        self._snapshot_memory(restored, actor_id=actor_id, change_note=change_note)
        self._record_event(
            memory_id=memory_id,
            event_type="restored",
            actor_id=actor_id,
            detail={"version": restored.version, "change_note": change_note},
        )
        return restored

    def list_history(self, memory_id: str) -> list[KnowledgeMemoryVersion]:
        rows = self._fetchall(
            """
            SELECT memory_id, version, scope_id, title, content, source, tags_json,
                   metadata_json, status, actor_id, change_note, snapshot_at
            FROM knowledge_memory_versions
            WHERE memory_id = %s
            ORDER BY version ASC
            """,
            (memory_id,),
        )
        return [self._map_history_row(row) for row in rows]
