from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from repositories.memory_repository import MemoryRepository


class FakeCursor:
    def __init__(self, rows=None, fetchone_queue=None, fetchall_queue=None):
        self.rows = rows or []
        self.fetchone_queue = list(fetchone_queue or [])
        self.fetchall_queue = list(fetchall_queue or [])
        self.executed = []

    def execute(self, sql, params):
        self.executed.append((sql.strip(), params))

    def fetchone(self):
        if self.fetchone_queue:
            return self.fetchone_queue.pop(0)
        return None

    def fetchall(self):
        if self.fetchall_queue:
            return self.fetchall_queue.pop(0)
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeMysql:
    def __init__(self, rows=None, fetchone_queue=None, fetchall_queue=None):
        self.cursor_obj = FakeCursor(rows, fetchone_queue, fetchall_queue)
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.ops = []

    def rpush(self, key, value):
        self.ops.append(("rpush", key, value))
        return self

    def ltrim(self, key, start, end):
        self.ops.append(("ltrim", key, start, end))
        return self

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))
        return self

    def execute(self):
        self.redis.ops.extend(self.ops)


class FakeRedis:
    def __init__(self):
        self.ops = []
        self.store = {}

    def pipeline(self):
        return FakePipeline(self)

    def lrange(self, key, start, end):
        return self.store.get(key, [])


def test_upsert_and_get_preferences():
    mysql = FakeMysql(
        fetchone_queue=[None],
        fetchall_queue=[[("theme", "dark"), ("lang", "zh")]],
    )
    repo = MemoryRepository(mysql, FakeRedis(), 86400, 100)

    repo.upsert_preference("u1", "theme", "dark")
    prefs = repo.get_preferences("u1")

    assert prefs == {"theme": "dark", "lang": "zh"}
    assert mysql.commits == 1


def test_append_and_get_session_messages():
    redis = FakeRedis()
    repo = MemoryRepository(FakeMysql(), redis, 86400, 100)

    repo.append_session_message("s1", "user: hello")
    redis.store["rag:session:s1:messages"] = ["user: hello"]
    assert repo.get_session_messages("s1") == ["user: hello"]
    assert redis.ops[0][0] == "rpush"
    assert redis.ops[1][0] == "ltrim"
    assert redis.ops[2][0] == "expire"


def test_delete_preference_writes_version():
    mysql = FakeMysql(fetchone_queue=[("dark", 0)])
    repo = MemoryRepository(mysql, FakeRedis(), 86400, 100)

    deleted = repo.delete_preference("u1", "theme", changed_by="tester", change_reason="cleanup")

    assert deleted is True
    assert mysql.commits == 1
    assert any("UPDATE user_preferences" in sql for sql, _ in mysql.cursor_obj.executed)
    assert any("INSERT INTO user_preference_versions" in sql for sql, _ in mysql.cursor_obj.executed)


def test_get_preference_history_returns_rows():
    mysql = FakeMysql(
        fetchall_queue=[
            [
                ("u1", "theme", 1, "create", None, "dark", "api", "upsert", "2026-05-26 10:00:00"),
                ("u1", "theme", 2, "delete", "dark", None, "api", "delete", "2026-05-26 11:00:00"),
            ]
        ]
    )
    repo = MemoryRepository(mysql, FakeRedis(), 86400, 100)

    rows = repo.get_preference_history("u1", "theme")

    assert len(rows) == 2
    assert rows[0][3] == "create"
    assert rows[1][3] == "delete"


def test_get_preferences_filters_deleted_records():
    mysql = FakeMysql(fetchall_queue=[[("theme", "dark")]])
    repo = MemoryRepository(mysql, FakeRedis(), 86400, 100)

    prefs = repo.get_preferences("u1")

    assert prefs == {"theme": "dark"}
    executed_sql = mysql.cursor_obj.executed[0][0]
    assert "is_deleted = 0" in executed_sql


def test_rollback_preference_restores_deleted_value():
    history_rows = [
        ("u1", "theme", 1, "create", None, "dark", "api", "upsert", "2026-05-26 10:00:00"),
        ("u1", "theme", 2, "delete", "dark", None, "api", "delete", "2026-05-26 11:00:00"),
    ]
    mysql = FakeMysql(fetchone_queue=[("dark", 1)], fetchall_queue=[history_rows])
    repo = MemoryRepository(mysql, FakeRedis(), 86400, 100)

    ok = repo.rollback_preference("u1", "theme", changed_by="tester", change_reason="rollback")

    assert ok is True
    assert mysql.commits == 1
    assert any("INSERT INTO user_preferences" in sql for sql, _ in mysql.cursor_obj.executed)
    assert any("INSERT INTO user_preference_versions" in sql for sql, _ in mysql.cursor_obj.executed)


def test_rollback_preference_returns_false_without_history():
    mysql = FakeMysql(fetchall_queue=[[]])
    repo = MemoryRepository(mysql, FakeRedis(), 86400, 100)

    ok = repo.rollback_preference("u1", "theme")

    assert ok is False


def test_metrics_snapshot_tracks_calls_and_failures():
    class FlakyMysql(FakeMysql):
        def __init__(self):
            super().__init__(rows=[("theme", "dark")])
            self.failures = 0

        def cursor(self):
            if self.failures < 1:
                self.failures += 1
                raise RuntimeError("temporary")
            return super().cursor()

    repo = MemoryRepository(
        mysql_client=FlakyMysql(),
        redis_client=FakeRedis(),
        session_ttl_seconds=86400,
        session_max_messages=100,
        retry_attempts=2,
        retry_backoff_seconds=0,
        op_alert_threshold_ms=1,
        failure_alert_threshold=1,
        monitor_enabled=False,
    )
    prefs = repo.get_preferences("u1")
    metrics = repo.get_metrics_snapshot()

    assert prefs == {"theme": "dark"}
    assert metrics["get_preferences"]["calls"] == 2
    assert metrics["get_preferences"]["failures"] == 1
