from fastapi import APIRouter

from core.config import settings
from schemas.common import HealthResponse, LivenessResponse
from services.container import (
    get_liveness_snapshot,
    get_memory_health_snapshot,
    get_readiness_snapshot,
)

router = APIRouter(tags=["health"])


def _build_health_response(snapshot: dict, *, include_memory: bool) -> HealthResponse:
    return HealthResponse(
        status=str(snapshot.get("overall_status", "ok")),
        app=settings.app_name,
        env=settings.app_env,
        overall_status=snapshot.get("overall_status"),
        dependencies=snapshot.get("dependencies"),
        memory=snapshot if include_memory else None,
    )


@router.get("/health/liveness", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    snapshot = get_liveness_snapshot()
    return LivenessResponse(
        status=str(snapshot.get("status", "ok")),
        app=settings.app_name,
        env=settings.app_env,
    )


@router.get("/health/readiness", response_model=HealthResponse)
def readiness() -> HealthResponse:
    snapshot = get_readiness_snapshot()
    return _build_health_response(snapshot, include_memory=False)


@router.get("/health/diagnostics", response_model=HealthResponse)
def diagnostics() -> HealthResponse:
    snapshot = get_memory_health_snapshot()
    return _build_health_response(snapshot, include_memory=True)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    snapshot = get_memory_health_snapshot()
    return _build_health_response(snapshot, include_memory=True)
