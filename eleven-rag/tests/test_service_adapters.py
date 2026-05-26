from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ingestion_service import IngestionService
from services.retrieval_service import RetrievalService
from services.chat_service import ChatService
from services.document_parser_service import DocumentParserService


def test_ingestion_service_delegates_pipeline(monkeypatch):
    class FakePipeline:
        def ingest(self, document_id, content, file_path, source):
            return (document_id, content, file_path, source)

    svc = IngestionService()
    svc._pipeline = FakePipeline()
    assert svc.ingest("d1", "c", None, "manual") == ("d1", "c", None, "manual")


def test_retrieval_service_delegates_qa():
    class FakeQA:
        def retrieve(self, query, top_k):
            return {"query": query, "top_k": top_k}

    svc = RetrievalService()
    svc._qa = FakeQA()
    assert svc.retrieve("q", 3) == {"query": "q", "top_k": 3}


def test_chat_service_delegates_qa():
    class FakeQA:
        def ask(self, user_id, session_id, query, top_k):
            return ("ok", [{"user_id": user_id, "session_id": session_id, "query": query, "top_k": top_k}])

    svc = ChatService()
    svc._qa = FakeQA()
    answer, sources = svc.ask("u1", "s1", "q", 2)
    assert answer == "ok"
    assert sources[0]["query"] == "q"


def test_document_parser_service_delegates_processor():
    class FakeProcessor:
        def parse_text(self, content):
            return content.strip()

        def parse_file_to_text(self, file_path):
            return f"parsed:{file_path}"

        def parse_file(self, file_path):
            return [file_path]

    svc = DocumentParserService()
    svc._processor = FakeProcessor()
    assert svc.parse_from_text(" hi ") == "hi"
    assert svc.parse_from_file("a.md") == "parsed:a.md"
    assert svc.load_documents_from_file("a.md") == ["a.md"]
