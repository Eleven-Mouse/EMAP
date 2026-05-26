from fastapi import APIRouter

from schemas.memory import PreferenceItem, PreferenceUpsertRequest
from rag_system import RAGSystem

router = APIRouter(tags=["memory"])
system = RAGSystem()


@router.post("/memory/preferences")
def upsert_preference(payload: PreferenceUpsertRequest) -> dict[str, str]:
    system.upsert_preference(
        user_id=payload.user_id,
        key=payload.key,
        value=payload.value,
    )
    return {"status": "ok"}


@router.get("/memory/preferences/{user_id}", response_model=list[PreferenceItem])
def list_preferences(user_id: str) -> list[PreferenceItem]:
    return system.list_preferences(user_id=user_id)
