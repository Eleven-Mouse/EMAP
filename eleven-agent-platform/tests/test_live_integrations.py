from pathlib import Path
import os
import sys
from uuid import uuid4

import pytest
import redis

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import settings
from repositories.memory_repository import MemoryRepository
from repositories.metadata_repository import MetadataRepository
from repositories.vector_repository import VectorRepository
from services.mysql_pool import PooledMySQLClient
from services.text_utils import hashed_vector


pytestmark = pytest.mark.integration

if os.getenv("EMAP_RUN_INTEGRATION_TESTS") != "1":
    pytest.skip(
        "集成测试默认跳过；设置 EMAP_RUN_INTEGRATION_TESTS=1 后才会连接真实 MySQL/Redis。",
        allow_module_level=True,
    )


class FakeEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [hashed_vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return hashed_vector(text)


def _build_mysql_client() -> PooledMySQLClient:
    client = PooledMySQLClient(
        dsn=settings.mysql_dsn,
        pool_size=1,
        max_overflow=1,
        pool_recycle_seconds=3600,
        pool_timeout_seconds=5,
    )
    try:
        with client.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001
        client.close()
        pytest.skip(f"MySQL 不可用，跳过真实集成测试: {exc}")
    return client


def _build_redis_client():
    client = redis.Redis.from_url(settings.redis_url, decode_responses=False)
    try:
        client.ping()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Redis 不可用，跳过真实集成测试: {exc}")
    return client


def _ensure_memory_schema(mysql_client: PooledMySQLClient) -> None:
    with mysql_client.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                user_id VARCHAR(128) NOT NULL,
                pref_key VARCHAR(128) NOT NULL,
                pref_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_user_pref (user_id, pref_key),
                KEY idx_user_pref_user_id (user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )


@pytest.fixture
def mysql_client():
    client = _build_mysql_client()
    yield client
    client.close()


@pytest.fixture
def metadata_repository(mysql_client: PooledMySQLClient):
    return MetadataRepository(
        mysql_client=mysql_client,
        retry_attempts=1,
        retry_backoff_seconds=0,
    )


@pytest.fixture
def redis_client():
    client = _build_redis_client()
    yield client


@pytest.fixture
def memory_repository(mysql_client: PooledMySQLClient, redis_client):
    _ensure_memory_schema(mysql_client)
    return MemoryRepository(
        mysql_client=mysql_client,
        redis_client=redis_client,
        session_ttl_seconds=300,
        session_max_messages=10,
        retry_attempts=1,
        retry_backoff_seconds=0,
        monitor_enabled=False,
    )


def _cleanup_document(mysql_client: PooledMySQLClient, document_id: str) -> None:
    with mysql_client.cursor() as cursor:
        cursor.execute("DELETE FROM documents WHERE document_id = %s", (document_id,))


def _cleanup_preferences(mysql_client: PooledMySQLClient, user_id: str) -> None:
    with mysql_client.cursor() as cursor:
        cursor.execute("DELETE FROM user_preferences WHERE user_id = %s", (user_id,))


def _build_vector_repository(tmp_path: Path) -> VectorRepository:
    repository = VectorRepository(
        index_path=str(tmp_path / "faiss.index"),
        mapping_path=str(tmp_path / "faiss_mapping.json"),
        embedding_model_name="test-hashed-embedder",
        embedding_cache_dir=str(tmp_path / "models"),
        embedding_device="cpu",
    )
    repository._embedder = FakeEmbedder()
    return repository


def test_live_mysql_metadata_replace_chunks(metadata_repository: MetadataRepository, mysql_client: PooledMySQLClient):
    document_id = f"it-doc-{uuid4().hex[:8]}"
    try:
        first = metadata_repository.replace_chunks(
            document_id=document_id,
            source="integration-test",
            chunks=[("第一版内容", {"version": 1})],
        )
        second = metadata_repository.replace_chunks(
            document_id=document_id,
            source="integration-test",
            chunks=[
                ("第二版内容-1", {"version": 2}),
                ("第二版内容-2", {"version": 2}),
            ],
        )
        chunks = metadata_repository.list_chunks_by_doc(document_id)

        assert first == 1
        assert second == 2
        assert [chunk.chunk_id for chunk in chunks] == [
            f"{document_id}-chunk-0",
            f"{document_id}-chunk-1",
        ]
        assert [chunk.content for chunk in chunks] == ["第二版内容-1", "第二版内容-2"]
    finally:
        _cleanup_document(mysql_client, document_id)


def test_live_memory_repository_uses_mysql_and_redis(
    memory_repository: MemoryRepository,
    mysql_client: PooledMySQLClient,
    redis_client,
):
    user_id = f"it-user-{uuid4().hex[:8]}"
    session_id = f"it-session-{uuid4().hex[:8]}"
    session_key = f"rag:session:{session_id}:messages"
    try:
        memory_repository.upsert_preference(user_id, "tone", "concise")
        memory_repository.upsert_preference(user_id, "style", "grounded")
        prefs = memory_repository.get_preferences(user_id)

        memory_repository.append_session_message(session_id, "user: hi")
        memory_repository.append_session_message(session_id, "assistant: hello")
        messages = memory_repository.get_session_messages(session_id)

        assert prefs == {"tone": "concise", "style": "grounded"}
        assert messages == ["user: hi", "assistant: hello"]
    finally:
        _cleanup_preferences(mysql_client, user_id)
        redis_client.delete(session_key)


def test_live_faiss_repository_can_rebuild_from_mysql_chunks(
    metadata_repository: MetadataRepository,
    mysql_client: PooledMySQLClient,
    tmp_path: Path,
):
    document_id = f"it-faiss-{uuid4().hex[:8]}"
    try:
        metadata_repository.replace_chunks(
            document_id=document_id,
            source="integration-test",
            chunks=[
                ("FAISS 负责向量索引与近邻检索。", {"topic": "vector"}),
                ("Redis 负责短时会话缓存。", {"topic": "memory"}),
            ],
        )
        stored_chunks = metadata_repository.list_chunks_by_doc(document_id)
        items = [(chunk.chunk_id, chunk.content) for chunk in stored_chunks]

        repository = _build_vector_repository(tmp_path)
        repository.index_chunks(items)

        reloaded = _build_vector_repository(tmp_path)
        hits = reloaded.query("FAISS 向量检索", top_k=2)
        assert hits
        assert hits[0].chunk_id == f"{document_id}-chunk-0"

        chunk_ids = [chunk.chunk_id for chunk in stored_chunks]
        reloaded.remove_document_chunks(chunk_ids)
        assert reloaded.query("FAISS 向量检索", top_k=2) == []

        rebuilt = _build_vector_repository(tmp_path)
        rebuilt.index_chunks(items)
        rebuilt_hits = rebuilt.query("FAISS 向量检索", top_k=2)
        assert rebuilt_hits
        assert rebuilt_hits[0].chunk_id == f"{document_id}-chunk-0"
    finally:
        _cleanup_document(mysql_client, document_id)
