from contextlib import contextmanager

from sqlalchemy import create_engine


class PooledMySQLClient:
    def __init__(
        self,
        dsn: str,
        pool_size: int,
        max_overflow: int,
        pool_recycle_seconds: int,
        pool_timeout_seconds: int = 30,
    ) -> None:
        self._engine = create_engine(
            dsn,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle_seconds,
            pool_timeout=pool_timeout_seconds,
            pool_pre_ping=True,
        )

    @contextmanager
    def cursor(self):
        connection = self._engine.raw_connection()
        cursor = connection.cursor()
        try:
            yield cursor
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def commit(self) -> None:
        # Compatibility no-op: cursor() already owns commit / rollback lifecycle.
        return None

    def close(self) -> None:
        self._engine.dispose()

    def ping(self) -> None:
        with self.cursor() as cursor:
            cursor.execute("SELECT 1")

    def pool_status(self) -> dict[str, int]:
        pool = self._engine.pool
        status: dict[str, int] = {}

        size = getattr(pool, "size", None)
        if callable(size):
            status["size"] = int(size())

        checked_in = getattr(pool, "checkedin", None)
        if callable(checked_in):
            status["checked_in"] = int(checked_in())

        checked_out = getattr(pool, "checkedout", None)
        if callable(checked_out):
            status["checked_out"] = int(checked_out())

        overflow = getattr(pool, "overflow", None)
        if callable(overflow):
            status["overflow"] = int(overflow())

        return status
