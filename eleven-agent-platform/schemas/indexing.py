from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class IndexJobItem(BaseModel):
    job_id: str
    job_type: str
    entity_id: str
    action: str
    status: str
    payload: dict[str, Any]
    attempts: int
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class IngestJobRequest(BaseModel):
    document_id: str = Field(..., description="Unique id for the document")
    content: str | None = Field(default=None, min_length=1)
    file_path: str | None = Field(default=None, description="Local file path")
    source: str = Field(default="manual")
    chunk_strategy: Literal["recursive", "markdown", "sentence"] = Field(
        default="recursive"
    )
    chunk_size: int | None = Field(default=None, ge=100, le=8000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=4000)

    @model_validator(mode="after")
    def validate_payload(self):
        if not self.content and not self.file_path:
            raise ValueError("Either content or file_path must be provided")
        if self.chunk_size is not None and self.chunk_overlap is not None:
            if self.chunk_overlap >= self.chunk_size:
                raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self
