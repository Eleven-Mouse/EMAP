from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from document_processing.pipeline import Pipeline  # noqa: E402


class FakeChunk:
    def __init__(self, chunk_id: str, content: str) -> None:
        self.chunk_id = chunk_id
        self.content = content


class FakeMetadataRepository:
    def __init__(self) -> None:
        self.replaced_chunks: list[tuple[str, dict]] = []
        self.documents: dict[str, list[tuple[str, dict]]] = {}

    def list_chunks_by_doc(self, document_id: str):
        if document_id in self.documents:
            chunks = self.documents[document_id]
            return [
                FakeChunk(chunk_id=f"{document_id}-chunk-{idx}", content=text)
                for idx, (text, _) in enumerate(chunks)
            ]
        return []

    def replace_chunks(self, document_id: str, source: str, chunks: list[tuple[str, dict]]) -> int:
        self.replaced_chunks = chunks
        self.documents[document_id] = chunks
        return len(chunks)

    def delete_document(self, document_id: str) -> bool:
        return self.documents.pop(document_id, None) is not None


class FakeVectorRepository:
    def __init__(self) -> None:
        self.removed: list[str] = []
        self.indexed: list[tuple[str, str]] = []

    def remove_document_chunks(self, chunk_ids: list[str]) -> None:
        self.removed = list(chunk_ids)

    def index_chunks(self, items: list[tuple[str, str]]) -> None:
        self.indexed = list(items)


def _build_pipeline() -> tuple[Pipeline, FakeMetadataRepository, FakeVectorRepository]:
    metadata = FakeMetadataRepository()
    vector = FakeVectorRepository()
    pipe = Pipeline()
    pipe._get_repositories = lambda: (metadata, vector)  # noqa: PLW2901
    return pipe, metadata, vector


@pytest.mark.parametrize("strategy", ["recursive", "markdown", "sentence"])
def test_ingest_supports_multiple_chunk_strategies(strategy: str):
    pipeline, metadata, _ = _build_pipeline()
    content = "# Title\n\n第一段。第二段！第三段？\n\n## H2\n内容A。内容B。"

    count = pipeline.ingest(
        document_id="doc-1",
        content=content,
        file_path=None,
        source="manual",
        chunk_strategy=strategy,
        chunk_size=80,
        chunk_overlap=10,
    )

    assert count > 0
    assert all(meta.get("chunk_strategy") == strategy for _, meta in metadata.replaced_chunks)


def test_ingest_rejects_invalid_chunk_strategy():
    pipeline, _, _ = _build_pipeline()
    with pytest.raises(ValueError):
        pipeline.ingest(
            document_id="doc-1",
            content="hello world",
            file_path=None,
            source="manual",
            chunk_strategy="invalid",
            chunk_size=200,
            chunk_overlap=20,
        )


def test_ingest_rejects_invalid_overlap():
    pipeline, _, _ = _build_pipeline()
    with pytest.raises(ValueError):
        pipeline.ingest(
            document_id="doc-1",
            content="hello world",
            file_path=None,
            source="manual",
            chunk_strategy="recursive",
            chunk_size=200,
            chunk_overlap=200,
        )


def test_delete_document_removes_metadata_and_vectors():
    pipeline, metadata, vector = _build_pipeline()
    pipeline.ingest(
        document_id="doc-1",
        content="第一段。第二段。",
        file_path=None,
        source="manual",
        chunk_strategy="recursive",
        chunk_size=50,
        chunk_overlap=0,
    )

    deleted_count = pipeline.delete_document("doc-1")

    assert deleted_count > 0
    assert metadata.list_chunks_by_doc("doc-1") == []
    assert len(vector.removed) == deleted_count
