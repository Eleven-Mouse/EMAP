from dataclasses import dataclass
from typing import Any


@dataclass
class ChunkRecord:
    chunk_id: str
    document_id: str
    content: str
    source: str
    metadata: dict[str, Any]


class DocumentRepository:
    """
    MVP repository.
    - In production, replace with MySQL for metadata and a vector DB for embeddings.
    """

    def __init__(self) -> None:
        self._chunks: list[ChunkRecord] = []

    def save_chunks(self, chunks: list[ChunkRecord]) -> None:
        self._chunks.extend(chunks)

    def list_chunks(self) -> list[ChunkRecord]:
        return list(self._chunks)

    def list_chunks_by_doc(self, document_id: str) -> list[ChunkRecord]:
        return [c for c in self._chunks if c.document_id == document_id]
