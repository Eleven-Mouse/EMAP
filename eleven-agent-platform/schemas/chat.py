from pydantic import BaseModel, Field

from schemas.common import SourceItem


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    top_k: int | None = None
    doc_id_prefixes: list[str] | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
