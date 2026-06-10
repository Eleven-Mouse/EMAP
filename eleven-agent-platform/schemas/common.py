from pydantic import BaseModel


class SourceItem(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    score: float
    source_type: str = "document_chunk"
    memory_id: str | None = None
    scope_id: str | None = None


class DependencyHealth(BaseModel):
    status: str
    detail: str | None = None
    latency_ms: float | None = None
    backend: str | None = None


class LivenessResponse(BaseModel):
    status: str
    app: str
    env: str


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
    overall_status: str | None = None
    dependencies: dict[str, DependencyHealth] | None = None
    memory: dict | None = None
