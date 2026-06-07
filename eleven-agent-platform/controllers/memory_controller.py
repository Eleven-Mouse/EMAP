from fastapi import APIRouter, HTTPException

from agent_system import AgentSystem
from schemas.knowledge import (
    KnowledgeMemoryActionRequest,
    KnowledgeMemoryCreateRequest,
    KnowledgeMemoryHistoryItem,
    KnowledgeMemoryItem,
    KnowledgeMemoryUpdateRequest,
)
from schemas.memory import PreferenceItem, PreferenceUpsertRequest

router = APIRouter(tags=["memory"])
system = AgentSystem()


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


@router.post("/memory/knowledge", response_model=KnowledgeMemoryItem, status_code=201)
def create_knowledge_memory(payload: KnowledgeMemoryCreateRequest) -> KnowledgeMemoryItem:
    try:
        return system.create_knowledge_memory(
            memory_id=payload.memory_id,
            scope_id=payload.scope_id,
            title=payload.title,
            content=payload.content,
            source=payload.source,
            tags=payload.tags,
            metadata=payload.metadata,
            actor_id=payload.actor_id,
            change_note=payload.change_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/memory/knowledge", response_model=list[KnowledgeMemoryItem])
def list_knowledge_memories(scope_prefix: str | None = None) -> list[KnowledgeMemoryItem]:
    scope_prefixes = None if scope_prefix is None else [scope_prefix]
    return system.list_knowledge_memories(scope_prefixes=scope_prefixes)


@router.get("/memory/knowledge/{memory_id}", response_model=KnowledgeMemoryItem)
def get_knowledge_memory(memory_id: str) -> KnowledgeMemoryItem:
    try:
        return system.get_knowledge_memory(memory_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/memory/knowledge/{memory_id}", response_model=KnowledgeMemoryItem)
def update_knowledge_memory(
    memory_id: str,
    payload: KnowledgeMemoryUpdateRequest,
) -> KnowledgeMemoryItem:
    try:
        return system.update_knowledge_memory(
            memory_id=memory_id,
            actor_id=payload.actor_id,
            change_note=payload.change_note,
            title=payload.title,
            content=payload.content,
            source=payload.source,
            tags=payload.tags,
            metadata=payload.metadata,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/memory/knowledge/{memory_id}", response_model=KnowledgeMemoryItem)
def delete_knowledge_memory(
    memory_id: str,
    payload: KnowledgeMemoryActionRequest,
) -> KnowledgeMemoryItem:
    try:
        return system.delete_knowledge_memory(
            memory_id=memory_id,
            actor_id=payload.actor_id,
            change_note=payload.change_note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/memory/knowledge/{memory_id}/restore", response_model=KnowledgeMemoryItem)
def restore_knowledge_memory(
    memory_id: str,
    payload: KnowledgeMemoryActionRequest,
) -> KnowledgeMemoryItem:
    try:
        return system.restore_knowledge_memory(
            memory_id=memory_id,
            actor_id=payload.actor_id,
            change_note=payload.change_note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/memory/knowledge/{memory_id}/history",
    response_model=list[KnowledgeMemoryHistoryItem],
)
def list_knowledge_memory_history(memory_id: str) -> list[KnowledgeMemoryHistoryItem]:
    return system.list_knowledge_memory_history(memory_id)
