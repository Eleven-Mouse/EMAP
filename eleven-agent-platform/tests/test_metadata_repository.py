from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from repositories.metadata_repository import MetadataRepository  # noqa: E402


class FakeCursor:
    def __init__(self, fetch_rows=None, rowcount=1):
        self.fetch_rows = fetch_rows or []
        self.rowcount = rowcount
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql.strip(), params))

    def executemany(self, sql, values):
        self.executed.append((sql.strip(), list(values)))

    def fetchall(self):
        return self.fetch_rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeMysql:
    def __init__(self, fetch_rows=None, rowcount=1):
        self.cursor_obj = FakeCursor(fetch_rows, rowcount=rowcount)
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1


def test_replace_and_list_chunks():
    mysql = FakeMysql(
        fetch_rows=[
            ("c1", "d1", "hello", "src", 0, '{"filetype":"text/markdown"}'),
        ]
    )
    repo = MetadataRepository(mysql)
    repo.replace_chunks("d1", "src", [("hello", {"filetype": "text/markdown"})])
    chunks = repo.list_chunks_by_doc("d1")

    assert chunks[0].chunk_id == "c1"
    assert mysql.commits >= 1


def test_retry_then_succeed():
    class FlakyMysql(FakeMysql):
        def __init__(self):
            super().__init__(fetch_rows=[("c1", "d1", "hello", "src", 0, "{}")])
            self.failures = 0

        def cursor(self):
            if self.failures < 2:
                self.failures += 1
                raise RuntimeError("temporary db issue")
            return super().cursor()

    repo = MetadataRepository(FlakyMysql(), retry_attempts=3, retry_backoff_seconds=0)
    chunks = repo.list_chunks_by_doc("d1")

    assert chunks[0].chunk_id == "c1"


def test_delete_document_returns_true_when_rows_affected():
    mysql = FakeMysql(rowcount=1)
    repo = MetadataRepository(mysql)
    deleted = repo.delete_document("d1")
    assert deleted is True


def test_delete_document_returns_false_when_no_rows_affected():
    mysql = FakeMysql(rowcount=0)
    repo = MetadataRepository(mysql)
    deleted = repo.delete_document("missing")
    assert deleted is False
