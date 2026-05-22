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

    def dispose(self):
        return None


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
