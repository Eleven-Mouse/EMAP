from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qa.answering import IntelligentQA


class EmptyMetadataRepository:
    def list_chunks(self):
        return []


class EmptyVectorRepository:
    def query(self, text: str, top_k: int):
        return []


class FakeKnowledgeMemory:
    def __init__(self, memory_id: str, scope_id: str, title: str, content: str) -> None:
        self.memory_id = memory_id
        self.scope_id = scope_id
        self.title = title
        self.content = content
        self.source = "manual"
        self.tags = ["knowledge"]
        self.metadata = {"kind": "memory"}


class FakeKnowledgeRepository:
    def __init__(self) -> None:
        self._memories = [
            FakeKnowledgeMemory(
                memory_id="km-rag",
                scope_id="team-knowledge",
                title="RAG约定",
                content="回答前先检索证据，再组织带引用的答案。",
            ),
            FakeKnowledgeMemory(
                memory_id="km-secret",
                scope_id="team-secret",
                title="私有约定",
                content="这条知识只给特定范围看。",
            ),
        ]

    def list_active_memories(self, scope_prefixes=None):
        if not scope_prefixes:
            return list(self._memories)
        return [
            item
            for item in self._memories
            if any(item.scope_id.startswith(prefix) for prefix in scope_prefixes)
        ]


class FakeMemoryService:
    def __init__(self) -> None:
        self.sessions = []

    def list_preferences(self, user_id: str):
        return []

    def append_session(self, session_id: str, message: str) -> None:
        self.sessions.append((session_id, message))


class FakeAuditLogger:
    def __init__(self) -> None:
        self.records = []

    def log(self, payload: dict) -> None:
        self.records.append(dict(payload))


def test_knowledge_memory_is_retrievable_and_visible_in_answer(monkeypatch):
    qa = IntelligentQA()
    qa._get_repositories = lambda: (EmptyMetadataRepository(), EmptyVectorRepository())
    qa._knowledge_repository = FakeKnowledgeRepository()
    qa._memory_service = FakeMemoryService()
    qa._audit_logger = FakeAuditLogger()

    monkeypatch.setattr("qa.answering.settings.hybrid_bm25_enabled", True)
    monkeypatch.setattr("qa.answering.settings.hybrid_vector_enabled", False)
    monkeypatch.setattr("qa.answering.settings.hybrid_reranker_enabled", False)
    monkeypatch.setattr("qa.answering.settings.llm_enabled", False)
    monkeypatch.setattr("qa.answering.settings.authz_enabled", False)

    answer, sources = qa.ask(
        user_id="u1",
        session_id="s1",
        query="RAG 回答前要做什么？",
        top_k=2,
        doc_id_prefixes=["team-knowledge"],
    )

    assert sources
    assert sources[0].source_type == "knowledge_memory"
    assert sources[0].chunk_id == "km-rag"
    assert sources[0].document_id == "team-knowledge"
    assert "km-rag" in answer
    assert qa.get_last_trace()["retrieved_source_types"] == ["knowledge_memory"]
