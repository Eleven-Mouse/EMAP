from time import perf_counter

try:
    import redis
except ImportError:  # pragma: no cover - exercised only in constrained test envs
    redis = None

from core.app_logging import get_logger
from core.config import settings
from repositories.document_repository import DocumentRepository
from repositories.index_job_repository import IndexJobRepository
from repositories.knowledge_repository import KnowledgeRepository
from repositories.metadata_repository import MetadataRepository
from repositories.memory_repository import MemoryRepository
from repositories.vector_repository import VectorRepository
from services.mysql_pool import PooledMySQLClient

logger = get_logger(__name__)


class UnavailableComponent:
    def __init__(self, name: str, error: Exception) -> None:
        self.name = name
        self.error = error

    def __getattr__(self, item: str):
        raise RuntimeError(f"{self.name} is unavailable: {self.error}") from self.error


def _build_component(name: str, factory):
    try:
        return factory()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "component_init_failed",
            extra={"event": "component_init_failed", "component": name, "detail": str(exc)},
        )
        return UnavailableComponent(name=name, error=exc)

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
metadata_repository = _build_component(
    "metadata_repository",
    lambda: MetadataRepository(
        mysql_client=mysql_client,
        retry_attempts=settings.mysql_retry_attempts,
        retry_backoff_seconds=settings.mysql_retry_backoff_seconds,
    ),
)
knowledge_repository = _build_component(
    "knowledge_repository",
    lambda: KnowledgeRepository(
        mysql_client=mysql_client,
        retry_attempts=settings.mysql_retry_attempts,
        retry_backoff_seconds=settings.mysql_retry_backoff_seconds,
    ),
)
index_job_repository = _build_component(
    "index_job_repository",
    lambda: IndexJobRepository(
        mysql_client=mysql_client,
        retry_attempts=settings.mysql_retry_attempts,
        retry_backoff_seconds=settings.mysql_retry_backoff_seconds,
    ),
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


def _dependency_ok(latency_ms: float | None = None, **extra) -> dict:
    payload = {"status": "ok"}
    if latency_ms is not None:
        payload["latency_ms"] = round(latency_ms, 2)
    payload.update(extra)
    return payload


def _dependency_error(name: str, detail: str) -> dict:
    logger.warning(
        "dependency_probe_failed",
        extra={"event": "dependency_probe_failed", "dependency": name, "detail": detail},
    )
    return {"status": "degraded", "detail": detail}


def _probe_mysql() -> dict:
    start = perf_counter()
    try:
        mysql_client.ping()
    except Exception as exc:  # noqa: BLE001
        return _dependency_error("mysql", str(exc))
    return _dependency_ok(latency_ms=(perf_counter() - start) * 1000)


def _probe_redis() -> dict:
    if redis_client is None:
        return {"status": "degraded", "detail": "redis client unavailable"}
    start = perf_counter()
    try:
        redis_client.ping()
    except Exception as exc:  # noqa: BLE001
        return _dependency_error("redis", str(exc))
    return _dependency_ok(latency_ms=(perf_counter() - start) * 1000)


def _probe_vector_backend() -> dict:
    backend_name = getattr(vector_repository, "backend_name", None)
    if backend_name is None:
        backend_name = getattr(vector_repository, "name", "unknown")
    return _dependency_ok(backend=str(backend_name))


def get_memory_health_snapshot() -> dict:
    mysql_status = mysql_client.pool_status()
    dependencies = {
        "mysql": _probe_mysql(),
        "redis": _probe_redis(),
        "vector_store": _probe_vector_backend(),
    }

    redis_status: dict[str, int] = {}
    pool = getattr(redis_client, "connection_pool", None)
    if pool is not None:
        in_use = getattr(pool, "_in_use_connections", None)
        available = getattr(pool, "_available_connections", None)
        if isinstance(in_use, set):
            redis_status["in_use"] = len(in_use)
        if isinstance(available, list):
            redis_status["available"] = len(available)

    try:
        index_jobs = index_job_repository.summarize_statuses()
    except Exception as exc:  # noqa: BLE001
        dependencies["index_jobs"] = _dependency_error("index_jobs", str(exc))
        index_jobs = {}
    else:
        dependencies["index_jobs"] = _dependency_ok()

    overall_status = (
        "ok"
        if all(item.get("status") == "ok" for item in dependencies.values())
        else "degraded"
    )
    return {
        "overall_status": overall_status,
        "dependencies": dependencies,
        "mysql_pool": mysql_status,
        "redis_pool": redis_status,
        "memory_metrics": memory_repository.get_metrics_snapshot(),
        "index_jobs": index_jobs,
        "vector_backend": settings.vector_backend,
    }
