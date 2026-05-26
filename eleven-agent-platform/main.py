from fastapi import FastAPI

from controllers.chat_controller import router as chat_router
from controllers.health_controller import router as health_router
from controllers.ingestion_controller import router as ingestion_router
from controllers.memory_controller import router as memory_router
from controllers.retrieval_controller import router as retrieval_router
from core.config import settings
from agent_system import AgentSystem

app = FastAPI(title=settings.app_name)
agent_system = AgentSystem()

app.include_router(health_router)
app.include_router(ingestion_router, prefix="/v1")
app.include_router(retrieval_router, prefix="/v1")
app.include_router(chat_router, prefix="/v1")
app.include_router(memory_router, prefix="/v1")


@app.on_event("startup")
def warmup_vector_store() -> None:
    try:
        agent_system.warmup_embedding()
    except Exception as exc:
        print(f"[warmup-warning] {exc}")

