from fastapi import APIRouter

from schemas.memory import (
    PreferenceDeleteRequest,
    PreferenceHistoryItem,
    PreferenceItem,
    PreferenceRollbackRequest,
    PreferenceUpsertRequest,
)
from agent_system import AgentSystem

router = APIRouter(tags=["memory"])
system = AgentSystem()


@router.post("/memory/preferences")
def upsert_preference(payload: PreferenceUpsertRequest) -> dict[str, str]:
    system.upsert_preference(
        user_id=payload.user_id,
        key=payload.key,
        value=payload.value,
        changed_by=payload.changed_by,
        change_reason=payload.change_reason,
    )
    return {"status": "ok"}


@router.get("/memory/preferences/{user_id}", response_model=list[PreferenceItem])
def list_preferences(user_id: str) -> list[PreferenceItem]:
    return system.list_preferences(user_id=user_id)


@router.delete("/memory/preferences")
def delete_preference(payload: PreferenceDeleteRequest) -> dict[str, str]:
    deleted = system.delete_preference(
        user_id=payload.user_id,
        key=payload.key,
        changed_by=payload.changed_by,
        change_reason=payload.change_reason,
    )
    if not deleted:
        return {"status": "not_found"}
    return {"status": "ok"}


@router.get(
    "/memory/preferences/{user_id}/{key}/history",
    response_model=list[PreferenceHistoryItem],
)
def get_preference_history(user_id: str, key: str) -> list[PreferenceHistoryItem]:
    return system.get_preference_history(user_id=user_id, key=key)


@router.post("/memory/preferences/rollback")
def rollback_preference(payload: PreferenceRollbackRequest) -> dict[str, str]:
    rolled_back = system.rollback_preference(
        user_id=payload.user_id,
        key=payload.key,
        target_version=payload.target_version,
        changed_by=payload.changed_by,
        change_reason=payload.change_reason,
    )
    if not rolled_back:
        return {"status": "not_found"}
    return {"status": "ok"}

