from typing import Literal

from pydantic import BaseModel, Field, model_validator


class IngestRequest(BaseModel):
    document_id: str = Field(..., description="Unique id for the document")
    content: str | None = Field(default=None, min_length=1)
    file_path: str | None = Field(default=None, description="Local file path")
    source: str = Field(default="manual")
    chunk_strategy: Literal["recursive", "markdown", "sentence"] = Field(
        default="recursive",
        description="Chunking strategy, inspired by Dify-style selectable chunking",
    )
    chunk_size: int | None = Field(
        default=None,
        ge=100,
        le=8000,
        description="Optional override for chunk size",
    )
    chunk_overlap: int | None = Field(
        default=None,
        ge=0,
        le=4000,
        description="Optional override for chunk overlap",
    )

    @model_validator(mode="after")
    def validate_payload(self):
        if not self.content and not self.file_path:
            raise ValueError("Either content or file_path must be provided")
        if self.chunk_size is not None and self.chunk_overlap is not None:
            if self.chunk_overlap >= self.chunk_size:
                raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class IngestResponse(BaseModel):
    document_id: str
    chunk_count: int


class DeleteDocumentResponse(BaseModel):
    document_id: str
    deleted_chunk_count: int
    status: str
