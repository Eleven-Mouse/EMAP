from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys
from dataclasses import dataclass

from sqlalchemy import create_engine

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT / "eleven-agent-platform") not in sys.path:
    sys.path.insert(0, str(ROOT / "eleven-agent-platform"))

from core.config import settings  # noqa: E402


SCHEMA_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    module_name VARCHAR(64) NOT NULL,
    version_tag VARCHAR(64) NOT NULL,
    script_name VARCHAR(255) NOT NULL,
    script_sha256 CHAR(64) NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_schema_migration (module_name, version_tag)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
"""


@dataclass(frozen=True)
class MigrationScript:
    version_tag: str
    path: pathlib.Path


def _script_sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_sql_statements(content: str) -> list[str]:
    statements = [stmt.strip() for stmt in content.split(";")]
    return [stmt for stmt in statements if stmt]


def _load_scripts() -> list[MigrationScript]:
    return [
        MigrationScript(
            version_tag="v1_init_user_preferences",
            path=ROOT / "scripts" / "init_mysql_memory.sql",
        ),
        MigrationScript(
            version_tag="v2_init_knowledge_memory",
            path=ROOT / "scripts" / "init_mysql_knowledge_memory.sql",
        ),
        MigrationScript(
            version_tag="v3_init_index_jobs",
            path=ROOT / "scripts" / "init_mysql_index_jobs.sql",
        ),
    ]


def _ensure_schema_table(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(SCHEMA_TABLE_SQL)
    connection.commit()


def _is_applied(connection, module_name: str, version_tag: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM schema_migrations
            WHERE module_name = %s AND version_tag = %s
            LIMIT 1
            """,
            (module_name, version_tag),
        )
        return cursor.fetchone() is not None


def _record_applied(
    connection,
    module_name: str,
    script: MigrationScript,
    script_sha256: str,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO schema_migrations(module_name, version_tag, script_name, script_sha256)
            VALUES(%s, %s, %s, %s)
            """,
            (module_name, script.version_tag, script.path.name, script_sha256),
        )
    connection.commit()


def _apply_script(connection, module_name: str, script: MigrationScript) -> str:
    script_sha = _script_sha256(script.path)
    sql = script.path.read_text(encoding="utf-8")
    statements = _parse_sql_statements(sql)

    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)
    connection.commit()

    _record_applied(connection, module_name, script, script_sha)
    return script_sha


def run(action: str, dry_run: bool) -> int:
    module_name = "memory"
    engine = create_engine(settings.mysql_dsn, pool_pre_ping=True)
    scripts = _load_scripts()

    with engine.raw_connection() as connection:
        _ensure_schema_table(connection)

        if action == "status":
            for script in scripts:
                applied = _is_applied(connection, module_name, script.version_tag)
                marker = "APPLIED" if applied else "PENDING"
                print(f"{marker} {script.version_tag} {script.path.name}")
            return 0

        for script in scripts:
            applied = _is_applied(connection, module_name, script.version_tag)
            if applied:
                print(f"SKIP {script.version_tag} {script.path.name}")
                continue

            if dry_run:
                print(f"DRY-RUN APPLY {script.version_tag} {script.path.name}")
                continue

            script_sha = _apply_script(connection, module_name, script)
            print(f"APPLY {script.version_tag} {script.path.name} sha256={script_sha}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage memory MySQL schema migrations")
    parser.add_argument(
        "--action",
        choices=["status", "apply"],
        default="apply",
        help="status: view migration state; apply: execute pending scripts",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show pending scripts without executing SQL",
    )
    args = parser.parse_args()
    return run(action=args.action, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

