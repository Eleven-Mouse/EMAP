from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from repositories.memory_repository import MemoryRepository


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []

    def execute(self, sql, params):
        self.executed.append((sql.strip(), params))

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeMysql:
    def __init__(self, rows=None):
        self.cursor_obj = FakeCursor(rows)
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
    mysql = FakeMysql(rows=[("theme", "dark"), ("lang", "zh")])
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
