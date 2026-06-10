from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI

from agent_system import AgentSystem
from controllers.chat_controller import router as chat_router
from controllers.health_controller import router as health_router
from controllers.ingestion_controller import router as ingestion_router
from controllers.memory_controller import router as memory_router
from controllers.retrieval_controller import router as retrieval_router
from core.app_logging import configure_logging, get_logger
from core.config import settings

configure_logging(settings.log_level)
logger = get_logger(__name__)

app = FastAPI(title=settings.app_name)
agent_system = AgentSystem()

app.include_router(health_router)
app.include_router(ingestion_router, prefix="/v1")
app.include_router(retrieval_router, prefix="/v1")
app.include_router(chat_router, prefix="/v1")
app.include_router(memory_router, prefix="/v1")


@app.middleware("http")
async def log_request_metrics(request, call_next):
    trace_id = request.headers.get("x-request-id", uuid4().hex[:16])
    start = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "http_request_failed",
            extra={
                "event": "http_request",
                "trace_id": trace_id,
                "stage": "http_request",
                "method": request.method,
                "path": request.url.path,
            },
        )
        raise

    duration_ms = (perf_counter() - start) * 1000
    response.headers["x-request-id"] = trace_id
    logger.info(
        "http_request_completed",
        extra={
            "event": "http_request",
            "trace_id": trace_id,
            "stage": "http_request",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )
    return response


@app.on_event("startup")
def warmup_vector_store() -> None:
    try:
        agent_system.warmup_embedding()
    except Exception as exc:
        logger.warning(
            "embedding_warmup_failed",
            extra={
                "event": "embedding_warmup_failed",
                "stage": "startup",
                "degrade_reason": "embedding_warmup_failed",
                "detail": str(exc),
            },
        )
