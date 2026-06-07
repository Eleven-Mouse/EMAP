from pydantic import BaseModel


class SourceItem(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    score: float
    source_type: str = "document_chunk"
    memory_id: str | None = None
    scope_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
    memory: dict | None = None
