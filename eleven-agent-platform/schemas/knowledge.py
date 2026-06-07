from typing import Any

from pydantic import BaseModel, Field


class KnowledgeMemoryCreateRequest(BaseModel):
    memory_id: str | None = Field(default=None, min_length=1)
    scope_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    source: str = Field(default="manual", min_length=1, max_length=255)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    actor_id: str = Field(..., min_length=1)
    change_note: str = Field(default="", max_length=255)


class KnowledgeMemoryUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1)
    source: str | None = Field(default=None, min_length=1, max_length=255)
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    actor_id: str = Field(..., min_length=1)
    change_note: str = Field(default="", max_length=255)


class KnowledgeMemoryActionRequest(BaseModel):
    actor_id: str = Field(..., min_length=1)
    change_note: str = Field(default="", max_length=255)


class KnowledgeMemoryItem(BaseModel):
    memory_id: str
    scope_id: str
    title: str
    content: str
    source: str
    tags: list[str]
    metadata: dict[str, Any]
    status: str
    version: int
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None


class KnowledgeMemoryHistoryItem(BaseModel):
    memory_id: str
    version: int
    scope_id: str
    title: str
    content: str
    source: str
    tags: list[str]
    metadata: dict[str, Any]
    status: str
    actor_id: str
    change_note: str
    snapshot_at: str | None = None
