from uuid import uuid4

from repositories.knowledge_repository import KnowledgeMemoryVersion, StoredKnowledgeMemory
from schemas.knowledge import KnowledgeMemoryHistoryItem, KnowledgeMemoryItem
from schemas.memory import PreferenceItem


class MemoryService:
    def __init__(self) -> None:
        self._indexing_service = None

    def _get_memory_repository(self):
        from services.container import memory_repository

        return memory_repository

    def _get_knowledge_repository(self):
        from services.container import knowledge_repository

        return knowledge_repository

    def _get_indexing_service(self):
        if self._indexing_service is None:
            from services.indexing_service import IndexingService

            self._indexing_service = IndexingService()
        return self._indexing_service

    @staticmethod
    def _to_knowledge_item(memory: StoredKnowledgeMemory) -> KnowledgeMemoryItem:
        return KnowledgeMemoryItem(
            memory_id=memory.memory_id,
            scope_id=memory.scope_id,
            title=memory.title,
            content=memory.content,
            source=memory.source,
            tags=list(memory.tags),
            metadata=dict(memory.metadata),
            status=memory.status,
            version=memory.version,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            deleted_at=memory.deleted_at,
        )

    @staticmethod
    def _to_history_item(version: KnowledgeMemoryVersion) -> KnowledgeMemoryHistoryItem:
        return KnowledgeMemoryHistoryItem(
            memory_id=version.memory_id,
            version=version.version,
            scope_id=version.scope_id,
            title=version.title,
            content=version.content,
            source=version.source,
            tags=list(version.tags),
            metadata=dict(version.metadata),
            status=version.status,
            actor_id=version.actor_id,
            change_note=version.change_note,
            snapshot_at=version.snapshot_at,
        )

    def upsert_preference(self, user_id: str, key: str, value: str) -> None:
        self._get_memory_repository().upsert_preference(user_id, key, value)

    def list_preferences(self, user_id: str) -> list[PreferenceItem]:
        prefs = self._get_memory_repository().get_preferences(user_id)
        return [
            PreferenceItem(user_id=user_id, key=key, value=value)
            for key, value in prefs.items()
        ]

    def append_session(self, session_id: str, message: str) -> None:
        self._get_memory_repository().append_session_message(session_id, message)

    def get_session(self, session_id: str) -> list[str]:
        return self._get_memory_repository().get_session_messages(session_id)

    def create_knowledge_memory(
        self,
        scope_id: str,
        title: str,
        content: str,
        source: str,
        tags: list[str],
        metadata: dict,
        actor_id: str,
        change_note: str = "",
        memory_id: str | None = None,
    ) -> KnowledgeMemoryItem:
        created = self._get_knowledge_repository().create_memory(
            memory_id=memory_id or f"km-{uuid4().hex[:12]}",
            scope_id=scope_id,
            title=title,
            content=content,
            source=source,
            tags=tags,
            metadata=metadata,
            actor_id=actor_id,
            change_note=change_note,
        )
        self._get_indexing_service().submit_knowledge_job(
            memory_id=created.memory_id,
            action="upsert",
        )
        return self._to_knowledge_item(created)

    def update_knowledge_memory(
        self,
        memory_id: str,
        actor_id: str,
        change_note: str = "",
        title: str | None = None,
        content: str | None = None,
        source: str | None = None,
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> KnowledgeMemoryItem:
        updated = self._get_knowledge_repository().update_memory(
            memory_id=memory_id,
            actor_id=actor_id,
            change_note=change_note,
            title=title,
            content=content,
            source=source,
            tags=tags,
            metadata=metadata,
        )
        self._get_indexing_service().submit_knowledge_job(
            memory_id=updated.memory_id,
            action="upsert",
        )
        return self._to_knowledge_item(updated)

    def get_knowledge_memory(self, memory_id: str) -> KnowledgeMemoryItem:
        memory = self._get_knowledge_repository().get_memory(memory_id)
        if memory is None:
            raise KeyError(f"Knowledge memory not found: {memory_id}")
        return self._to_knowledge_item(memory)

    def list_knowledge_memories(
        self,
        scope_prefixes: list[str] | None = None,
    ) -> list[KnowledgeMemoryItem]:
        memories = self._get_knowledge_repository().list_active_memories(
            scope_prefixes=scope_prefixes
        )
        return [self._to_knowledge_item(memory) for memory in memories]

    def delete_knowledge_memory(
        self,
        memory_id: str,
        actor_id: str,
        change_note: str = "",
    ) -> KnowledgeMemoryItem:
        deleted = self._get_knowledge_repository().soft_delete_memory(
            memory_id=memory_id,
            actor_id=actor_id,
            change_note=change_note,
        )
        self._get_indexing_service().submit_knowledge_job(
            memory_id=deleted.memory_id,
            action="delete",
        )
        return self._to_knowledge_item(deleted)

    def restore_knowledge_memory(
        self,
        memory_id: str,
        actor_id: str,
        change_note: str = "",
    ) -> KnowledgeMemoryItem:
        restored = self._get_knowledge_repository().restore_memory(
            memory_id=memory_id,
            actor_id=actor_id,
            change_note=change_note,
        )
        self._get_indexing_service().submit_knowledge_job(
            memory_id=restored.memory_id,
            action="upsert",
        )
        return self._to_knowledge_item(restored)

    def list_knowledge_memory_history(
        self,
        memory_id: str,
    ) -> list[KnowledgeMemoryHistoryItem]:
        history = self._get_knowledge_repository().list_history(memory_id)
        return [self._to_history_item(item) for item in history]
