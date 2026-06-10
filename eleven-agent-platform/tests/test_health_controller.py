from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import controllers.health_controller as health_controller


def test_health_endpoints(monkeypatch):
    monkeypatch.setattr(health_controller, "get_liveness_snapshot", lambda: {"status": "ok"})
    monkeypatch.setattr(
        health_controller,
        "get_readiness_snapshot",
        lambda: {
            "overall_status": "degraded",
            "dependencies": {"mysql": {"status": "degraded", "detail": "down"}},
        },
    )
    monkeypatch.setattr(
        health_controller,
        "get_memory_health_snapshot",
        lambda: {
            "overall_status": "ok",
            "dependencies": {"mysql": {"status": "ok"}},
            "mysql_pool": {"size": 5},
        },
    )

    app = FastAPI()
    app.include_router(health_controller.router)
    client = TestClient(app)

    liveness = client.get("/health/liveness")
    readiness = client.get("/health/readiness")
    diagnostics = client.get("/health/diagnostics")
    legacy = client.get("/health")

    assert liveness.status_code == 200
    assert liveness.json()["status"] == "ok"

    assert readiness.status_code == 200
    assert readiness.json()["status"] == "degraded"
    assert readiness.json()["memory"] is None
    assert readiness.json()["dependencies"]["mysql"]["status"] == "degraded"

    assert diagnostics.status_code == 200
    assert diagnostics.json()["status"] == "ok"
    assert diagnostics.json()["memory"]["mysql_pool"]["size"] == 5

    assert legacy.status_code == 200
    assert legacy.json()["memory"]["mysql_pool"]["size"] == 5
