from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import services.container as container


class FakeMysqlClient:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    def pool_status(self):
        return {"size": 5, "checked_in": 4, "checked_out": 1, "overflow": 0}

    def ping(self):
        if self.should_fail:
            raise RuntimeError("mysql unavailable")


class FakeRedisPool:
    def __init__(self):
        self._in_use_connections = {"a"}
        self._available_connections = ["b", "c"]


class FakeRedisClient:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.connection_pool = FakeRedisPool()

    def ping(self):
        if self.should_fail:
            raise RuntimeError("redis unavailable")


class FakeMemoryRepository:
    def get_metrics_snapshot(self):
        return {
            "get_preferences": {"calls": 1, "failures": 0, "slow_calls": 0, "avg_ms": 1.2}
        }


class FakeIndexJobRepository:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    def summarize_statuses(self):
        if self.should_fail:
            raise RuntimeError("index jobs unavailable")
        return {"ready": 2, "failed": 1}


class FakeVectorRepository:
    backend_name = "memory"


def test_health_snapshot_reports_ok(monkeypatch):
    monkeypatch.setattr(container, "mysql_client", FakeMysqlClient())
    monkeypatch.setattr(container, "redis_client", FakeRedisClient())
    monkeypatch.setattr(container, "memory_repository", FakeMemoryRepository())
    monkeypatch.setattr(container, "index_job_repository", FakeIndexJobRepository())
    monkeypatch.setattr(container, "vector_repository", FakeVectorRepository())

    snapshot = container.get_memory_health_snapshot()

    assert snapshot["overall_status"] == "ok"
    assert snapshot["dependencies"]["mysql"]["status"] == "ok"
    assert snapshot["dependencies"]["redis"]["status"] == "ok"
    assert snapshot["dependencies"]["vector_store"]["backend"] == "memory"
    assert snapshot["index_jobs"]["ready"] == 2


def test_health_snapshot_reports_degraded(monkeypatch):
    monkeypatch.setattr(container, "mysql_client", FakeMysqlClient(should_fail=True))
    monkeypatch.setattr(container, "redis_client", FakeRedisClient(should_fail=True))
    monkeypatch.setattr(container, "memory_repository", FakeMemoryRepository())
    monkeypatch.setattr(
        container,
        "index_job_repository",
        FakeIndexJobRepository(should_fail=True),
    )
    monkeypatch.setattr(container, "vector_repository", FakeVectorRepository())

    snapshot = container.get_memory_health_snapshot()

    assert snapshot["overall_status"] == "degraded"
    assert snapshot["dependencies"]["mysql"]["status"] == "degraded"
    assert snapshot["dependencies"]["redis"]["status"] == "degraded"
    assert snapshot["dependencies"]["index_jobs"]["status"] == "degraded"
    assert snapshot["index_jobs"] == {}
