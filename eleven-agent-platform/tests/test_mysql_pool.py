from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.mysql_pool import PooledMySQLClient


class FakePool:
    def size(self):
        return 5

    def checkedin(self):
        return 3

    def checkedout(self):
        return 2

    def overflow(self):
        return 1


class FakeEngine:
    def __init__(self):
        self.pool = FakePool()
        self.connection = FakeRawConnection()

    def dispose(self):
        return None

    def raw_connection(self):
        return self.connection


class FakeRawCursor:
    def __init__(self):
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)

    def close(self):
        return None


class FakeRawConnection:
    def __init__(self):
        self.cursor_obj = FakeRawCursor()
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_pool_status_from_engine_pool_metrics():
    client = PooledMySQLClient(
        dsn="mysql+pymysql://root:password@127.0.0.1:3306/db",
        pool_size=5,
        max_overflow=10,
        pool_recycle_seconds=3600,
        pool_timeout_seconds=30,
    )
    client._engine = FakeEngine()  # type: ignore[attr-defined]
    status = client.pool_status()

    assert status == {
        "size": 5,
        "checked_in": 3,
        "checked_out": 2,
        "overflow": 1,
    }


def test_ping_executes_simple_query():
    client = PooledMySQLClient(
        dsn="mysql+pymysql://root:password@127.0.0.1:3306/db",
        pool_size=5,
        max_overflow=10,
        pool_recycle_seconds=3600,
        pool_timeout_seconds=30,
    )
    client._engine = FakeEngine()  # type: ignore[attr-defined]

    client.ping()

    assert client._engine.connection.cursor_obj.executed == ["SELECT 1"]  # type: ignore[attr-defined]
