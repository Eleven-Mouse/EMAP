from pydantic import BaseModel


class SourceItem(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    score: float


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
    memory: dict | None = None
