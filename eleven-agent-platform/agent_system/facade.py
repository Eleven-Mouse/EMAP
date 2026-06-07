from document_processing.document_processor import DocumentProcessor
from document_processing.pipeline import Pipeline
from embedding.embedding_service import EmbeddingService
from qa.answering import IntelligentQA
from vector_storage.vector_store import FaissVectorStore


class AgentSystem:
    def __init__(self) -> None:
        self._document_processor: DocumentProcessor | None = None
        self._pipeline: Pipeline | None = None
        self._embedding_service: EmbeddingService | None = None
        self._vector_store: FaissVectorStore | None = None
        self._qa: IntelligentQA | None = None
        self._memory_service = None

    def _get_document_processor(self) -> DocumentProcessor:
        if self._document_processor is None:
            self._document_processor = DocumentProcessor()
        return self._document_processor

    def _get_pipeline(self) -> Pipeline:
        if self._pipeline is None:
            self._pipeline = Pipeline()
        return self._pipeline

    def _get_embedding_service(self) -> EmbeddingService:
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService()
        return self._embedding_service

    def _get_vector_store(self) -> FaissVectorStore:
        if self._vector_store is None:
            self._vector_store = FaissVectorStore()
        return self._vector_store

    def _get_qa(self) -> IntelligentQA:
        if self._qa is None:
            self._qa = IntelligentQA()
        return self._qa

    def _get_memory_service(self):
        if self._memory_service is None:
            from services.memory_service import MemoryService

            self._memory_service = MemoryService()
        return self._memory_service

    def parse_text(self, content: str) -> str:
        return self._get_document_processor().parse_text(content)

    def parse_file(self, file_path: str):
        return self._get_document_processor().parse_file(file_path)

    def ingest(
        self,
        document_id: str,
        content: str | None = None,
        file_path: str | None = None,
        source: str = "manual",
        chunk_strategy: str = "recursive",
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> int:
        return self._get_pipeline().ingest(
            document_id=document_id,
            content=content,
            file_path=file_path,
            source=source,
            chunk_strategy=chunk_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def warmup_embedding(self) -> None:
        self._get_embedding_service().warmup()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._get_embedding_service().embed_texts(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._get_embedding_service().embed_query(text)

    def add_texts(self, items: list[tuple[str, str]]) -> None:
        self._get_vector_store().add_texts(items)

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        self._get_vector_store().delete_by_chunk_ids(chunk_ids)

    def search(self, query: str, top_k: int):
        return self._get_vector_store().search(query, top_k)

    def retrieve(self, query: str, top_k: int):
        return self._get_qa().retrieve(query, top_k)

    def ask(
        self,
        user_id: str,
        session_id: str,
        query: str,
        top_k: int | None = None,
        doc_id_prefixes: list[str] | None = None,
    ):
        return self._get_qa().ask(
            user_id=user_id,
            session_id=session_id,
            query=query,
            top_k=top_k,
            doc_id_prefixes=doc_id_prefixes,
        )

    def get_last_trace(self) -> dict | None:
        return self._get_qa().get_last_trace()

    def upsert_preference(self, user_id: str, key: str, value: str) -> None:
        self._get_memory_service().upsert_preference(user_id, key, value)

    def list_preferences(self, user_id: str):
        return self._get_memory_service().list_preferences(user_id)

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
    ):
        return self._get_memory_service().create_knowledge_memory(
            scope_id=scope_id,
            title=title,
            content=content,
            source=source,
            tags=tags,
            metadata=metadata,
            actor_id=actor_id,
            change_note=change_note,
            memory_id=memory_id,
        )

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
    ):
        return self._get_memory_service().update_knowledge_memory(
            memory_id=memory_id,
            actor_id=actor_id,
            change_note=change_note,
            title=title,
            content=content,
            source=source,
            tags=tags,
            metadata=metadata,
        )

    def get_knowledge_memory(self, memory_id: str):
        return self._get_memory_service().get_knowledge_memory(memory_id)

    def list_knowledge_memories(self, scope_prefixes: list[str] | None = None):
        return self._get_memory_service().list_knowledge_memories(
            scope_prefixes=scope_prefixes
        )

    def delete_knowledge_memory(
        self,
        memory_id: str,
        actor_id: str,
        change_note: str = "",
    ):
        return self._get_memory_service().delete_knowledge_memory(
            memory_id=memory_id,
            actor_id=actor_id,
            change_note=change_note,
        )

    def restore_knowledge_memory(
        self,
        memory_id: str,
        actor_id: str,
        change_note: str = "",
    ):
        return self._get_memory_service().restore_knowledge_memory(
            memory_id=memory_id,
            actor_id=actor_id,
            change_note=change_note,
        )

    def list_knowledge_memory_history(self, memory_id: str):
        return self._get_memory_service().list_knowledge_memory_history(memory_id)

