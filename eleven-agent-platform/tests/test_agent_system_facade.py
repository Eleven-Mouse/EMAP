from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_system.facade import AgentSystem


class FakePipeline:
    def ingest(
        self,
        document_id,
        content,
        file_path,
        source,
        chunk_strategy,
        chunk_size,
        chunk_overlap,
    ):
        return (
            document_id,
            content,
            file_path,
            source,
            chunk_strategy,
            chunk_size,
            chunk_overlap,
        )


class FakeDocumentProcessor:
    def parse_text(self, content):
        return content.strip()

    def parse_file(self, file_path):
        return [file_path]


class FakeEmbeddingService:
    def warmup(self):
        return None

    def embed_texts(self, texts):
        return [[float(len(text))] for text in texts]

    def embed_query(self, text):
        return [float(len(text))]


class FakeVectorStore:
    def add_texts(self, items):
        return items

    def delete_by_chunk_ids(self, chunk_ids):
        return chunk_ids

    def search(self, query, top_k):
        return [(query, top_k)]


class FakeQA:
    def retrieve(self, query, top_k):
        return {"query": query, "top_k": top_k}

    def ask(self, user_id, session_id, query, top_k, doc_id_prefixes=None):
        return ("answer", [{"user_id": user_id, "session_id": session_id, "query": query, "top_k": top_k}])


class FakeMemoryService:
    def upsert_preference(self, user_id, key, value):
        return (user_id, key, value)

    def list_preferences(self, user_id):
        return [{"user_id": user_id, "key": "tone", "value": "grounded"}]

    def create_knowledge_memory(self, **kwargs):
        return {"action": "create", **kwargs}

    def update_knowledge_memory(self, **kwargs):
        return {"action": "update", **kwargs}

    def get_knowledge_memory(self, memory_id):
        return {"action": "get", "memory_id": memory_id}

    def list_knowledge_memories(self, scope_prefixes=None):
        return [{"action": "list", "scope_prefixes": scope_prefixes}]

    def delete_knowledge_memory(self, **kwargs):
        return {"action": "delete", **kwargs}

    def restore_knowledge_memory(self, **kwargs):
        return {"action": "restore", **kwargs}

    def list_knowledge_memory_history(self, memory_id):
        return [{"action": "history", "memory_id": memory_id}]


def test_agent_system_facade_delegates_to_layer_objects():
    rag = AgentSystem()
    rag._pipeline = FakePipeline()
    rag._document_processor = FakeDocumentProcessor()
    rag._embedding_service = FakeEmbeddingService()
    rag._vector_store = FakeVectorStore()
    rag._qa = FakeQA()
    rag._memory_service = FakeMemoryService()

    assert rag.parse_text("  hello  ") == "hello"
    assert rag.parse_file("a.pdf") == ["a.pdf"]
    assert rag.ingest("d1", "c", None, "manual", "markdown", 300, 30) == (
        "d1",
        "c",
        None,
        "manual",
        "markdown",
        300,
        30,
    )
    assert rag.embed_texts(["ab"]) == [[2.0]]
    assert rag.embed_query("abc") == [3.0]
    assert rag.search("q", 5) == [("q", 5)]
    assert rag.retrieve("q", 5) == {"query": "q", "top_k": 5}
    assert rag.ask("u1", "s1", "q", 5)[0] == "answer"
    assert rag.list_preferences("u1")[0]["key"] == "tone"
    assert rag.create_knowledge_memory(
        scope_id="team-a",
        title="A",
        content="B",
        source="manual",
        tags=[],
        metadata={},
        actor_id="alice",
    )["action"] == "create"
    assert rag.get_knowledge_memory("km-1")["memory_id"] == "km-1"
    assert rag.list_knowledge_memories(["team-a"])[0]["action"] == "list"
    assert rag.delete_knowledge_memory("km-1", "alice")["action"] == "delete"
    assert rag.restore_knowledge_memory("km-1", "alice")["action"] == "restore"
    assert rag.list_knowledge_memory_history("km-1")[0]["action"] == "history"

