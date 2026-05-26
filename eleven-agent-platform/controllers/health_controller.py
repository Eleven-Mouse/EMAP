from fastapi import APIRouter

from core.config import settings
from schemas.common import HealthResponse
from services.container import get_memory_health_snapshot

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    snapshot = get_memory_health_snapshot()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        env=settings.app_env,
        memory=snapshot,
    )
