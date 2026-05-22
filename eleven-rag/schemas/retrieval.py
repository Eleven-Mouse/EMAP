from pydantic import BaseModel, Field

from schemas.common import SourceItem


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int | None = None


class RetrieveResponse(BaseModel):
    query: str
    hits: list[SourceItem]
