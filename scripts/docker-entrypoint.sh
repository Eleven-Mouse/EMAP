#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/app"
cd "$ROOT_DIR"

echo "==> Waiting for MySQL and Redis"
uv run --python 3.12 python - <<'PY'
import sys
import time
from sqlalchemy import create_engine, text
import redis

sys.path.insert(0, "eleven-agent-platform")
from core.config import settings


def wait_mysql(retries: int = 30, delay: float = 2.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            engine = create_engine(settings.mysql_dsn, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("MySQL ok")
            return
        except Exception as exc:  # noqa: BLE001
            if attempt >= retries:
                raise RuntimeError(f"MySQL not ready after {retries} attempts: {exc}") from exc
            time.sleep(delay)


def wait_redis(retries: int = 30, delay: float = 2.0) -> None:
    client = redis.Redis.from_url(settings.redis_url)
    for attempt in range(1, retries + 1):
        try:
            if client.ping():
                print("Redis ok")
                return
        except Exception as exc:  # noqa: BLE001
            if attempt >= retries:
                raise RuntimeError(f"Redis not ready after {retries} attempts: {exc}") from exc
        time.sleep(delay)


wait_mysql()
wait_redis()
PY

echo "==> Apply memory schema"
uv run --python 3.12 python scripts/manage_memory_schema.py --action apply

echo "==> Start EMAP API"
exec uv run --python 3.12 uvicorn main:app --app-dir eleven-agent-platform --host 0.0.0.0 --port 8000
