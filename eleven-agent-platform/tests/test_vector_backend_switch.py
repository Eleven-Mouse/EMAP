from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from repositories.vector_repository import VectorRepository
from vector_storage import build_vector_backend


class FakeEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            if "apple" in text:
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.0, 1.0])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        if "apple" in text:
            return [1.0, 0.0]
        return [0.0, 1.0]


def test_vector_repository_supports_memory_backend(tmp_path: Path):
    repository = VectorRepository(
        index_path=str(tmp_path / "faiss.index"),
        mapping_path=str(tmp_path / "faiss_mapping.json"),
        embedding_model_name="fake",
        embedding_cache_dir=str(tmp_path / "models"),
        backend_name="memory",
    )
    repository._embedder = FakeEmbedder()

    repository.index_chunks(
        [("doc-apple", "apple phone camera"), ("doc-android", "android gaming")]
    )
    hits = repository.query("apple recommendation", top_k=2)

    assert repository.backend_name == "memory"
    assert hits[0].chunk_id == "doc-apple"
    repository.remove_document_chunks(["doc-apple"])
    assert all(hit.chunk_id != "doc-apple" for hit in repository.query("apple", 2))


def test_build_vector_backend_rejects_unknown_backend():
    with pytest.raises(ValueError):
        build_vector_backend(
            "unknown",
            index_path="unused",
            mapping_path="unused",
            qdrant_url="http://127.0.0.1:6333",
            qdrant_collection_name="test",
        )
