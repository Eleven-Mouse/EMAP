from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import controllers.chat_controller as chat_controller


class FakeSystem:
    def __init__(self) -> None:
        self.calls = []

    def ask(self, **kwargs):
        self.calls.append(kwargs)
        return (
            "ok",
            [
                {
                    "chunk_id": "doc-team-a-chunk-0",
                    "document_id": "doc-team-a",
                    "content": "系统采用基于证据的回答方式。",
                    "score": 0.95,
                    "source_type": "document_chunk",
                    "memory_id": None,
                    "scope_id": None,
                }
            ],
        )


def test_chat_endpoint_passes_trace_id(monkeypatch):
    fake_system = FakeSystem()
    monkeypatch.setattr(chat_controller, "system", fake_system)

    app = FastAPI()
    app.include_router(chat_controller.router, prefix="/v1")
    client = TestClient(app)

    response = client.post(
        "/v1/chat",
        headers={"x-request-id": "trace-controller-001"},
        json={
            "user_id": "u1",
            "session_id": "s1",
            "query": "系统采用什么回答方式？",
            "top_k": 3,
            "doc_id_prefixes": ["doc-team-a"],
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "ok"
    assert fake_system.calls[0]["trace_id"] == "trace-controller-001"
