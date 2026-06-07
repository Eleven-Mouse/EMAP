from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import controllers.ingestion_controller as ingestion_controller


class FakeIngestionService:
    def submit_ingest_job(self, **kwargs):
        return {
            "job_id": "idx-doc-001",
            "job_type": "document",
            "entity_id": kwargs["document_id"],
            "action": "upsert",
            "status": "pending",
            "payload": dict(kwargs),
            "attempts": 0,
            "error_message": None,
            "created_at": "2026-06-07T00:00:01Z",
            "updated_at": "2026-06-07T00:00:01Z",
            "started_at": None,
            "completed_at": None,
        }

    def get_ingest_job(self, job_id: str):
        if job_id == "idx-doc-001":
            return {
                "job_id": job_id,
                "job_type": "document",
                "entity_id": "doc-async",
                "action": "upsert",
                "status": "ready",
                "payload": {"document_id": "doc-async"},
                "attempts": 1,
                "error_message": None,
                "created_at": "2026-06-07T00:00:01Z",
                "updated_at": "2026-06-07T00:00:02Z",
                "started_at": "2026-06-07T00:00:01Z",
                "completed_at": "2026-06-07T00:00:02Z",
            }
        return None


def test_ingest_async_endpoints(monkeypatch):
    monkeypatch.setattr(ingestion_controller, "ingestion_service", FakeIngestionService())
    app = FastAPI()
    app.include_router(ingestion_controller.router, prefix="/v1")
    client = TestClient(app)

    create_resp = client.post(
        "/v1/ingest/jobs",
        json={
            "document_id": "doc-async",
            "content": "async indexing content",
            "source": "manual",
            "chunk_strategy": "recursive",
            "chunk_size": 200,
            "chunk_overlap": 20,
        },
    )
    get_resp = client.get("/v1/ingest/jobs/idx-doc-001")
    missing_resp = client.get("/v1/ingest/jobs/missing")

    assert create_resp.status_code == 202
    assert create_resp.json()["job_id"] == "idx-doc-001"
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "ready"
    assert missing_resp.status_code == 404
