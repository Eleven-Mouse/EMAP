from dataclasses import dataclass

import numpy as np

from vector_storage import build_vector_backend


@dataclass
class VectorHit:
    chunk_id: str
    score: float


class VectorRepository:
    def __init__(
        self,
        index_path: str,
        mapping_path: str,
        embedding_model_name: str,
        embedding_cache_dir: str,
        embedding_device: str = "cpu",
        backend_name: str = "faiss",
        qdrant_url: str = "http://127.0.0.1:6333",
        qdrant_collection_name: str = "eleven_rag_vectors",
    ) -> None:
        self.index_path = index_path
        self.mapping_path = mapping_path
        self.embedding_model_name = embedding_model_name
        self.embedding_cache_dir = embedding_cache_dir
        self.embedding_device = embedding_device
        self.backend_name = backend_name
        self.qdrant_url = qdrant_url
        self.qdrant_collection_name = qdrant_collection_name
        self._embedder = None
        self._backend = build_vector_backend(
            backend_name=self.backend_name,
            index_path=self.index_path,
            mapping_path=self.mapping_path,
            qdrant_url=self.qdrant_url,
            qdrant_collection_name=self.qdrant_collection_name,
        )

    def _get_embedder(self):
        if self._embedder is None:
            try:
                from langchain_huggingface import HuggingFaceEmbeddings
            except ImportError as exc:
                raise RuntimeError(
                    "langchain-huggingface and sentence-transformers are required."
                ) from exc
            self._embedder = HuggingFaceEmbeddings(
                model=self.embedding_model_name,
                cache_folder=self.embedding_cache_dir,
                model_kwargs={"device": self.embedding_device},
                encode_kwargs={"normalize_embeddings": True},
            )
        return self._embedder

    def warmup(self) -> None:
        try:
            self._get_embedder().embed_query("warmup")
        except Exception as exc:
            raise RuntimeError(
                "Embedding model warmup failed. Pre-download the model or retry with "
                "stable network access."
            ) from exc

    def index_chunks(self, items: list[tuple[str, str]]) -> None:
        if not items:
            return
        embedder = self._get_embedder()
        item_ids = [item_id for item_id, _ in items]
        texts = [content for _, content in items]
        vectors = np.array(embedder.embed_documents(texts), dtype="float32")
        self._backend.upsert(item_ids, vectors)

    def remove_document_chunks(self, chunk_ids: list[str]) -> None:
        self._backend.remove(chunk_ids)

    def query(self, text: str, top_k: int) -> list[VectorHit]:
        query_vector = np.array([self._get_embedder().embed_query(text)], dtype="float32")
        return [
            VectorHit(chunk_id=hit.item_id, score=hit.score)
            for hit in self._backend.query(query_vector, top_k)
        ]
