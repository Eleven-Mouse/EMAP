try:
    import redis
except ImportError:  # pragma: no cover - exercised only in constrained test envs
    redis = None

from core.config import settings
from repositories.document_repository import DocumentRepository
from repositories.index_job_repository import IndexJobRepository
from repositories.knowledge_repository import KnowledgeRepository
from repositories.metadata_repository import MetadataRepository
from repositories.memory_repository import MemoryRepository
from repositories.vector_repository import VectorRepository
from services.mysql_pool import PooledMySQLClient

document_repository = DocumentRepository()
vector_repository = VectorRepository(
    index_path=settings.faiss_index_path,
    mapping_path=settings.faiss_mapping_path,
    embedding_model_name=settings.embedding_model_name,
    embedding_cache_dir=settings.embedding_cache_dir,
    embedding_device=settings.embedding_device,
    backend_name=settings.vector_backend,
    qdrant_url=settings.qdrant_url,
    qdrant_collection_name=settings.qdrant_collection_name,
)

mysql_client = PooledMySQLClient(
    dsn=settings.mysql_dsn,
    pool_size=settings.mysql_pool_size,
    max_overflow=settings.mysql_max_overflow,
    pool_recycle_seconds=settings.mysql_pool_recycle_seconds,
    pool_timeout_seconds=settings.mysql_pool_timeout_seconds,
)
metadata_repository = MetadataRepository(
    mysql_client=mysql_client,
    retry_attempts=settings.mysql_retry_attempts,
    retry_backoff_seconds=settings.mysql_retry_backoff_seconds,
)
knowledge_repository = KnowledgeRepository(
    mysql_client=mysql_client,
    retry_attempts=settings.mysql_retry_attempts,
    retry_backoff_seconds=settings.mysql_retry_backoff_seconds,
)
index_job_repository = IndexJobRepository(
    mysql_client=mysql_client,
    retry_attempts=settings.mysql_retry_attempts,
    retry_backoff_seconds=settings.mysql_retry_backoff_seconds,
)
redis_client = (
    redis.Redis.from_url(
        settings.redis_url,
        decode_responses=False,
    )
    if redis is not None
    else None
)
memory_repository = MemoryRepository(
    mysql_client=mysql_client,
    redis_client=redis_client,
    session_ttl_seconds=settings.session_ttl_seconds,
    session_max_messages=settings.session_max_messages,
    retry_attempts=settings.memory_retry_attempts,
    retry_backoff_seconds=settings.memory_retry_backoff_seconds,
    op_alert_threshold_ms=settings.memory_op_alert_threshold_ms,
    failure_alert_threshold=settings.memory_failure_alert_threshold,
    monitor_enabled=settings.memory_monitor_enabled,
)


def get_memory_health_snapshot() -> dict:
    mysql_status = mysql_client.pool_status()

    redis_status: dict[str, int] = {}
    pool = getattr(redis_client, "connection_pool", None)
    if pool is not None:
        in_use = getattr(pool, "_in_use_connections", None)
        available = getattr(pool, "_available_connections", None)
        if isinstance(in_use, set):
            redis_status["in_use"] = len(in_use)
        if isinstance(available, list):
            redis_status["available"] = len(available)

    return {
        "mysql_pool": mysql_status,
        "redis_pool": redis_status,
        "memory_metrics": memory_repository.get_metrics_snapshot(),
        "index_jobs": index_job_repository.summarize_statuses(),
        "vector_backend": settings.vector_backend,
    }
