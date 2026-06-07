from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import controllers.memory_controller as memory_controller
from schemas.knowledge import KnowledgeMemoryHistoryItem, KnowledgeMemoryItem


class FakeSystem:
    def __init__(self) -> None:
        self.memory = KnowledgeMemoryItem(
            memory_id="km-api",
            scope_id="team-api",
            title="接口约定",
            content="所有关键回答必须带引用。",
            source="manual",
            tags=["api"],
            metadata={"owner": "backend"},
            status="active",
            version=1,
            created_at="2026-06-07T00:00:01Z",
            updated_at="2026-06-07T00:00:01Z",
            deleted_at=None,
        )

    def create_knowledge_memory(self, **kwargs):
        if kwargs.get("memory_id"):
            self.memory.memory_id = kwargs["memory_id"]
        self.memory.scope_id = kwargs["scope_id"]
        self.memory.title = kwargs["title"]
        self.memory.content = kwargs["content"]
        self.memory.tags = list(kwargs["tags"])
        self.memory.metadata = dict(kwargs["metadata"])
        return self.memory

    def list_knowledge_memories(self, scope_prefixes=None):
        if not scope_prefixes:
            return [self.memory]
        return [self.memory] if self.memory.scope_id.startswith(scope_prefixes[0]) else []

    def get_knowledge_memory(self, memory_id: str):
        if memory_id != self.memory.memory_id:
            raise KeyError(memory_id)
        return self.memory

    def update_knowledge_memory(self, memory_id: str, **kwargs):
        if memory_id != self.memory.memory_id:
            raise KeyError(memory_id)
        if kwargs.get("title") is not None:
            self.memory.title = kwargs["title"]
        if kwargs.get("content") is not None:
            self.memory.content = kwargs["content"]
        self.memory.version += 1
        return self.memory

    def delete_knowledge_memory(self, memory_id: str, **kwargs):
        if memory_id != self.memory.memory_id:
            raise KeyError(memory_id)
        self.memory.status = "deleted"
        self.memory.version += 1
        self.memory.deleted_at = "2026-06-07T00:00:02Z"
        return self.memory

    def restore_knowledge_memory(self, memory_id: str, **kwargs):
        if memory_id != self.memory.memory_id:
            raise KeyError(memory_id)
        self.memory.status = "active"
        self.memory.version += 1
        self.memory.deleted_at = None
        return self.memory

    def list_knowledge_memory_history(self, memory_id: str):
        return [
            KnowledgeMemoryHistoryItem(
                memory_id=memory_id,
                version=1,
                scope_id="team-api",
                title="接口约定",
                content="所有关键回答必须带引用。",
                source="manual",
                tags=["api"],
                metadata={"owner": "backend"},
                status="active",
                actor_id="alice",
                change_note="init",
                snapshot_at="2026-06-07T00:00:01Z",
            )
        ]


def test_knowledge_memory_endpoints(monkeypatch):
    fake_system = FakeSystem()
    monkeypatch.setattr(memory_controller, "system", fake_system)
    app = FastAPI()
    app.include_router(memory_controller.router, prefix="/v1")
    client = TestClient(app)

    create_resp = client.post(
        "/v1/memory/knowledge",
        json={
            "memory_id": "km-api",
            "scope_id": "team-api",
            "title": "接口约定",
            "content": "所有关键回答必须带引用。",
            "source": "manual",
            "tags": ["api"],
            "metadata": {"owner": "backend"},
            "actor_id": "alice",
            "change_note": "init",
        },
    )
    get_resp = client.get("/v1/memory/knowledge/km-api")
    list_resp = client.get("/v1/memory/knowledge", params={"scope_prefix": "team-api"})
    update_resp = client.put(
        "/v1/memory/knowledge/km-api",
        json={
            "title": "接口与引用约定",
            "actor_id": "bob",
            "change_note": "rename",
        },
    )
    delete_resp = client.request(
        "DELETE",
        "/v1/memory/knowledge/km-api",
        json={"actor_id": "bob", "change_note": "cleanup"},
    )
    restore_resp = client.post(
        "/v1/memory/knowledge/km-api/restore",
        json={"actor_id": "carol", "change_note": "restore"},
    )
    history_resp = client.get("/v1/memory/knowledge/km-api/history")

    assert create_resp.status_code == 201
    assert get_resp.status_code == 200
    assert list_resp.status_code == 200
    assert update_resp.status_code == 200
    assert delete_resp.status_code == 200
    assert restore_resp.status_code == 200
    assert history_resp.status_code == 200
    assert get_resp.json()["memory_id"] == "km-api"
    assert list_resp.json()[0]["scope_id"] == "team-api"
    assert update_resp.json()["version"] == 2
    assert delete_resp.json()["status"] == "deleted"
    assert restore_resp.json()["status"] == "active"
    assert history_resp.json()[0]["actor_id"] == "alice"


def test_get_knowledge_memory_returns_404(monkeypatch):
    fake_system = FakeSystem()
    monkeypatch.setattr(memory_controller, "system", fake_system)
    app = FastAPI()
    app.include_router(memory_controller.router, prefix="/v1")
    client = TestClient(app)

    response = client.get("/v1/memory/knowledge/km-missing")

    assert response.status_code == 404
