from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_system.facade import RAGSystem


class FakePipeline:
    def ingest(self, document_id, content, file_path, source):
        return (document_id, content, file_path, source)


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

    def ask(self, user_id, session_id, query, top_k):
        return ("answer", [{"user_id": user_id, "session_id": session_id, "query": query, "top_k": top_k}])


def test_rag_system_facade_delegates_to_layer_objects():
    rag = RAGSystem()
    rag._pipeline = FakePipeline()
    rag._document_processor = FakeDocumentProcessor()
    rag._embedding_service = FakeEmbeddingService()
    rag._vector_store = FakeVectorStore()
    rag._qa = FakeQA()

    assert rag.parse_text("  hello  ") == "hello"
    assert rag.parse_file("a.pdf") == ["a.pdf"]
    assert rag.ingest("d1", "c", None, "manual") == ("d1", "c", None, "manual")
    assert rag.embed_texts(["ab"]) == [[2.0]]
    assert rag.embed_query("abc") == [3.0]
    assert rag.search("q", 5) == [("q", 5)]
    assert rag.retrieve("q", 5) == {"query": "q", "top_k": 5}
    assert rag.ask("u1", "s1", "q", 5)[0] == "answer"
