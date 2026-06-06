from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from document_processing.pipeline import Pipeline
from qa.answering import IntelligentQA
from repositories.metadata_repository import StoredChunk


class InMemoryMetadataRepository:
    def __init__(self) -> None:
        self._documents: dict[str, list[StoredChunk]] = {}

    def list_chunks(self) -> list[StoredChunk]:
        chunks: list[StoredChunk] = []
        for doc_chunks in self._documents.values():
            chunks.extend(doc_chunks)
        return sorted(chunks, key=lambda item: (item.document_id, item.chunk_order))

    def list_chunks_by_doc(self, document_id: str) -> list[StoredChunk]:
        return list(self._documents.get(document_id, []))

    def replace_chunks(
        self,
        document_id: str,
        source: str,
        chunks: list[tuple[str, dict]],
    ) -> int:
        self._documents[document_id] = [
            StoredChunk(
                chunk_id=f"{document_id}-chunk-{idx}",
                document_id=document_id,
                content=content,
                source=source,
                chunk_order=idx,
            )
            for idx, (content, _) in enumerate(chunks)
        ]
        return len(self._documents[document_id])


class InMemoryVectorRepository:
    def __init__(self) -> None:
        self.removed_batches: list[list[str]] = []
        self.indexed_batches: list[list[tuple[str, str]]] = []

    def remove_document_chunks(self, chunk_ids: list[str]) -> None:
        self.removed_batches.append(list(chunk_ids))

    def index_chunks(self, items: list[tuple[str, str]]) -> None:
        self.indexed_batches.append(list(items))

    def query(self, text: str, top_k: int):
        return []


class FakeMemoryService:
    def __init__(self) -> None:
        self.sessions: list[tuple[str, str]] = []

    def list_preferences(self, user_id: str):
        return []

    def append_session(self, session_id: str, message: str) -> None:
        self.sessions.append((session_id, message))


class FakeAuditLogger:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def log(self, payload: dict) -> None:
        self.records.append(dict(payload))


def _build_shared_system() -> tuple[
    Pipeline,
    IntelligentQA,
    InMemoryMetadataRepository,
    InMemoryVectorRepository,
    FakeMemoryService,
    FakeAuditLogger,
]:
    metadata_repository = InMemoryMetadataRepository()
    vector_repository = InMemoryVectorRepository()
    memory_service = FakeMemoryService()
    audit_logger = FakeAuditLogger()

    pipeline = Pipeline()
    pipeline._get_repositories = lambda: (metadata_repository, vector_repository)  # noqa: PLW2901

    qa = IntelligentQA()
    qa._get_repositories = lambda: (metadata_repository, vector_repository)
    qa._memory_service = memory_service
    qa._audit_logger = audit_logger
    return (
        pipeline,
        qa,
        metadata_repository,
        vector_repository,
        memory_service,
        audit_logger,
    )


def test_ingest_retrieve_and_chat_share_the_same_document_state(monkeypatch):
    pipeline, qa, _, vector_repository, memory_service, audit_logger = _build_shared_system()

    monkeypatch.setattr("qa.answering.settings.hybrid_bm25_enabled", True)
    monkeypatch.setattr("qa.answering.settings.hybrid_vector_enabled", False)
    monkeypatch.setattr("qa.answering.settings.hybrid_reranker_enabled", False)
    monkeypatch.setattr("qa.answering.settings.llm_enabled", False)
    monkeypatch.setattr("qa.answering.settings.authz_enabled", False)

    chunk_count = pipeline.ingest(
        document_id="doc-rag",
        content="RAG 先检索证据，再结合证据生成回答。引用必须带 chunk_id。",
        file_path=None,
        source="manual",
        chunk_strategy="sentence",
        chunk_size=80,
        chunk_overlap=10,
    )

    hits = qa.retrieve("RAG 如何回答", top_k=2)
    answer, sources = qa.ask(
        user_id="u1",
        session_id="s1",
        query="RAG 如何回答？",
        top_k=2,
    )

    assert chunk_count >= 1
    assert hits
    assert hits[0].document_id == "doc-rag"
    assert len(sources) == len(hits)
    assert "doc-rag-chunk-0" in answer
    assert "检索证据" in answer
    assert vector_repository.indexed_batches[-1][0][0] == "doc-rag-chunk-0"
    assert memory_service.sessions[0] == ("s1", "user: RAG 如何回答？")
    assert memory_service.sessions[-1][0] == "s1"
    assert audit_logger.records[-1]["retrieved_chunk_ids"]


def test_reingest_replaces_old_chunks_and_updates_retrieval(monkeypatch):
    pipeline, qa, metadata_repository, vector_repository, _, _ = _build_shared_system()

    monkeypatch.setattr("qa.answering.settings.hybrid_bm25_enabled", True)
    monkeypatch.setattr("qa.answering.settings.hybrid_vector_enabled", False)
    monkeypatch.setattr("qa.answering.settings.hybrid_reranker_enabled", False)
    monkeypatch.setattr("qa.answering.settings.llm_enabled", False)
    monkeypatch.setattr("qa.answering.settings.authz_enabled", False)

    pipeline.ingest(
        document_id="doc-memory",
        content="旧版本答案强调模板回复。",
        file_path=None,
        source="manual",
        chunk_strategy="recursive",
        chunk_size=80,
        chunk_overlap=10,
    )
    old_chunk_ids = [
        chunk.chunk_id for chunk in metadata_repository.list_chunks_by_doc("doc-memory")
    ]

    pipeline.ingest(
        document_id="doc-memory",
        content="新版本答案强调混合检索、引用校验和安全降级。",
        file_path=None,
        source="manual",
        chunk_strategy="recursive",
        chunk_size=80,
        chunk_overlap=10,
    )

    hits = qa.retrieve("混合检索 怎么做", top_k=2)

    assert old_chunk_ids == ["doc-memory-chunk-0"]
    assert vector_repository.removed_batches[-1] == old_chunk_ids
    assert hits
    assert all("旧版本" not in hit.content for hit in hits)
    assert any("混合检索" in hit.content for hit in hits)
