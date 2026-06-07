"""Vector storage layer adapters."""

from vector_storage.faiss_backend import FaissVectorBackend
from vector_storage.memory_backend import MemoryVectorBackend
from vector_storage.qdrant_backend import QdrantVectorBackend


def build_vector_backend(
    backend_name: str,
    *,
    index_path: str,
    mapping_path: str,
    qdrant_url: str,
    qdrant_collection_name: str,
):
    normalized = str(backend_name or "faiss").strip().lower()
    if normalized == "faiss":
        return FaissVectorBackend(index_path=index_path, mapping_path=mapping_path)
    if normalized == "memory":
        return MemoryVectorBackend()
    if normalized == "qdrant":
        return QdrantVectorBackend(
            url=qdrant_url,
            collection_name=qdrant_collection_name,
        )
    raise ValueError(f"Unsupported vector backend: {backend_name}")
