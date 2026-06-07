from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from repositories.knowledge_repository import KnowledgeRepository


class FakeKnowledgeRepository(KnowledgeRepository):
    def __init__(self) -> None:
        super().__init__(mysql_client=object(), retry_attempts=1, retry_backoff_seconds=0)
        self._memories: dict[str, dict] = {}
        self._histories: list[dict] = []
        self._events: list[dict] = []
        self._clock = 0

    def _tick(self) -> str:
        self._clock += 1
        return f"2026-06-07T00:00:{self._clock:02d}Z"

    def _memory_row(self, item: dict) -> tuple:
        return (
            item["memory_id"],
            item["scope_id"],
            item["title"],
            item["content"],
            item["source"],
            item["tags_json"],
            item["metadata_json"],
            item["status"],
            item["version"],
            item["created_at"],
            item["updated_at"],
            item["deleted_at"],
        )

    def _execute(self, sql: str, params: tuple = ()) -> None:
        normalized = " ".join(sql.split())
        if normalized.startswith("INSERT INTO knowledge_memories("):
            now = self._tick()
            self._memories[params[0]] = {
                "memory_id": params[0],
                "scope_id": params[1],
                "title": params[2],
                "content": params[3],
                "source": params[4],
                "tags_json": params[5],
                "metadata_json": params[6],
                "status": "active",
                "version": 1,
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }
            return
        if normalized.startswith("UPDATE knowledge_memories SET title ="):
            memory = self._memories[params[6]]
            memory.update(
                {
                    "title": params[0],
                    "content": params[1],
                    "source": params[2],
                    "tags_json": params[3],
                    "metadata_json": params[4],
                    "version": params[5],
                    "status": "active",
                    "deleted_at": None,
                    "updated_at": self._tick(),
                }
            )
            return
        if "SET status = 'deleted'" in normalized:
            memory = self._memories[params[1]]
            memory.update(
                {
                    "status": "deleted",
                    "version": params[0],
                    "deleted_at": self._tick(),
                    "updated_at": f"2026-06-07T00:00:{self._clock:02d}Z",
                }
            )
            return
        if "SET status = 'active'" in normalized and "deleted_at = NULL" in normalized:
            memory = self._memories[params[1]]
            memory.update(
                {
                    "status": "active",
                    "version": params[0],
                    "deleted_at": None,
                    "updated_at": self._tick(),
                }
            )
            return
        if normalized.startswith("INSERT INTO knowledge_memory_versions("):
            self._histories.append(
                {
                    "memory_id": params[0],
                    "version": params[1],
                    "scope_id": params[2],
                    "title": params[3],
                    "content": params[4],
                    "source": params[5],
                    "tags_json": params[6],
                    "metadata_json": params[7],
                    "status": params[8],
                    "actor_id": params[9],
                    "change_note": params[10],
                    "snapshot_at": self._tick(),
                }
            )
            return
        if normalized.startswith("INSERT INTO knowledge_memory_events"):
            self._events.append(
                {
                    "memory_id": params[0],
                    "event_type": params[1],
                    "actor_id": params[2],
                    "detail_json": params[3],
                }
            )
            return
        raise AssertionError(f"Unsupported SQL in fake repository: {normalized}")

    def _fetchone(self, sql: str, params: tuple = ()) -> tuple | None:
        memory = self._memories.get(params[0])
        if memory is None:
            return None
        if "AND status = 'active'" in sql and memory["status"] != "active":
            return None
        return self._memory_row(memory)

    def _fetchall(self, sql: str, params: tuple = ()) -> list[tuple]:
        normalized = " ".join(sql.split())
        if "FROM knowledge_memories" in normalized:
            rows = [
                self._memory_row(memory)
                for memory in self._memories.values()
                if memory["status"] == "active"
            ]
            rows.sort(key=lambda row: (row[10], row[0]), reverse=True)
            return rows
        if "FROM knowledge_memory_versions" in normalized:
            rows = [
                (
                    item["memory_id"],
                    item["version"],
                    item["scope_id"],
                    item["title"],
                    item["content"],
                    item["source"],
                    item["tags_json"],
                    item["metadata_json"],
                    item["status"],
                    item["actor_id"],
                    item["change_note"],
                    item["snapshot_at"],
                )
                for item in self._histories
                if item["memory_id"] == params[0]
            ]
            rows.sort(key=lambda row: row[1])
            return rows
        raise AssertionError(f"Unsupported query in fake repository: {normalized}")


def test_knowledge_repository_full_lifecycle():
    repo = FakeKnowledgeRepository()

    created = repo.create_memory(
        memory_id="km-001",
        scope_id="team-alpha",
        title="部署约定",
        content="服务变更前先看健康检查。",
        source="manual",
        tags=["ops"],
        metadata={"level": "team"},
        actor_id="alice",
        change_note="initial create",
    )
    updated = repo.update_memory(
        memory_id="km-001",
        title="部署与发布约定",
        actor_id="bob",
        change_note="clarify title",
    )
    deleted = repo.soft_delete_memory(
        memory_id="km-001",
        actor_id="bob",
        change_note="cleanup",
    )
    restored = repo.restore_memory(
        memory_id="km-001",
        actor_id="carol",
        change_note="restore for reuse",
    )
    history = repo.list_history("km-001")

    assert created.version == 1
    assert updated.version == 2
    assert deleted.status == "deleted"
    assert restored.status == "active"
    assert [item.version for item in history] == [1, 2, 3, 4]
    assert [item.actor_id for item in history] == ["alice", "bob", "bob", "carol"]
    assert [event["event_type"] for event in repo._events] == [
        "created",
        "updated",
        "deleted",
        "restored",
    ]


def test_knowledge_repository_filters_deleted_and_scope_prefix():
    repo = FakeKnowledgeRepository()
    repo.create_memory(
        memory_id="km-a",
        scope_id="team-a",
        title="A",
        content="alpha memory",
        source="manual",
        tags=[],
        metadata={},
        actor_id="alice",
    )
    repo.create_memory(
        memory_id="km-b",
        scope_id="team-b",
        title="B",
        content="beta memory",
        source="manual",
        tags=[],
        metadata={},
        actor_id="bob",
    )
    repo.soft_delete_memory("km-b", actor_id="bob", change_note="remove")

    memories = repo.list_active_memories(scope_prefixes=["team-a"])

    assert [item.memory_id for item in memories] == ["km-a"]


def test_knowledge_repository_rejects_empty_update():
    repo = FakeKnowledgeRepository()
    repo.create_memory(
        memory_id="km-empty",
        scope_id="team-a",
        title="A",
        content="alpha",
        source="manual",
        tags=[],
        metadata={},
        actor_id="alice",
    )

    try:
        repo.update_memory(memory_id="km-empty", actor_id="alice")
    except ValueError as exc:
        assert "at least one changed field" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty update")
