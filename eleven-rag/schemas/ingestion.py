from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    document_id: str = Field(..., description="Unique id for the document")
    content: str | None = Field(default=None, min_length=1)
    file_path: str | None = Field(default=None, description="Local file path")
    source: str = Field(default="manual")


class IngestResponse(BaseModel):
    document_id: str
    chunk_count: int
