from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ingestion_service import IngestionService
from services.retrieval_service import RetrievalService
from services.chat_service import ChatService
from services.document_parser_service import DocumentParserService


def test_ingestion_service_delegates_pipeline(monkeypatch):
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

    svc = IngestionService()
    svc._pipeline = FakePipeline()
    assert svc.ingest("d1", "c", None, "manual", "sentence", 256, 32) == (
        "d1",
        "c",
        None,
        "manual",
        "sentence",
        256,
        32,
    )


def test_ingestion_service_delegates_index_job_submission():
    class FakeIndexingService:
        def submit_document_job(self, **kwargs):
            return {"job_id": "idx-1", **kwargs}

    svc = IngestionService()
    svc._indexing_service = FakeIndexingService()
    result = svc.submit_ingest_job("d1", "c", None, "manual", "sentence", 256, 32)

    assert result["job_id"] == "idx-1"
    assert result["document_id"] == "d1"


def test_retrieval_service_delegates_qa():
    class FakeQA:
        def retrieve(self, query, top_k):
            return {"query": query, "top_k": top_k}

    svc = RetrievalService()
    svc._qa = FakeQA()
    assert svc.retrieve("q", 3) == {"query": "q", "top_k": 3}


def test_chat_service_delegates_qa():
    class FakeQA:
        def ask(self, user_id, session_id, query, top_k, doc_id_prefixes=None, trace_id=None):
            return ("ok", [{"user_id": user_id, "session_id": session_id, "query": query, "top_k": top_k, "doc_id_prefixes": doc_id_prefixes}])

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
