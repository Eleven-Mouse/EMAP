import json
import pathlib
from dataclasses import dataclass

import numpy as np


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
    ) -> None:
        self.index_path = index_path
        self.mapping_path = mapping_path
        self.embedding_model_name = embedding_model_name
        self.embedding_cache_dir = embedding_cache_dir
        self.embedding_device = embedding_device
        self._faiss = None
        self._index = None
        self._embedder = None
        self._chunk_id_to_faiss_id: dict[str, int] = {}
        self._next_faiss_id = 1
        self._load()

    def _get_faiss(self):
        if self._faiss is None:
            try:
                import faiss
            except ImportError as exc:
                raise RuntimeError(
                    "faiss-cpu is required for vector search. Run `uv sync`."
                ) from exc
            self._faiss = faiss
        return self._faiss

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

    def _make_index(self, dim: int):
        faiss = self._get_faiss()
        base = faiss.IndexFlatIP(dim)
        return faiss.IndexIDMap2(base)

    def _load(self) -> None:
        faiss = self._get_faiss()
        index_path = pathlib.Path(self.index_path)
        mapping_path = pathlib.Path(self.mapping_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)

        if index_path.exists() and mapping_path.exists():
            self._index = faiss.read_index(str(index_path))
            payload = json.loads(mapping_path.read_text(encoding="utf-8"))
            self._chunk_id_to_faiss_id = {
                str(k): int(v) for k, v in payload.get("chunk_id_to_faiss_id", {}).items()
            }
            self._next_faiss_id = int(payload.get("next_faiss_id", 1))
            return

        self._index = None

    def _persist(self) -> None:
        faiss = self._get_faiss()
        index_path = pathlib.Path(self.index_path)
        mapping_path = pathlib.Path(self.mapping_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(index_path))
        mapping_path.write_text(
            json.dumps(
                {
                    "chunk_id_to_faiss_id": self._chunk_id_to_faiss_id,
                    "next_faiss_id": self._next_faiss_id,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def index_chunks(self, items: list[tuple[str, str]]) -> None:
        if not items:
            return
        embedder = self._get_embedder()
        texts = [content for _, content in items]
        vectors = np.array(embedder.embed_documents(texts), dtype="float32")
        if self._index is None:
            self._index = self._make_index(vectors.shape[1])
        ids = np.array(
            [self._allocate_faiss_id(chunk_id) for chunk_id, _ in items],
            dtype="int64",
        )
        self._index.add_with_ids(vectors, ids)
        self._persist()

    def _allocate_faiss_id(self, chunk_id: str) -> int:
        existing = self._chunk_id_to_faiss_id.get(chunk_id)
        if existing is not None:
            return existing
        faiss_id = self._next_faiss_id
        self._next_faiss_id += 1
        self._chunk_id_to_faiss_id[chunk_id] = faiss_id
        return faiss_id

    def remove_document_chunks(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        faiss = self._get_faiss()
        ids = [
            self._chunk_id_to_faiss_id.pop(chunk_id)
            for chunk_id in chunk_ids
            if chunk_id in self._chunk_id_to_faiss_id
        ]
        if not ids:
            return
        self._index.remove_ids(np.array(ids, dtype="int64"))
        self._persist()

    def query(self, text: str, top_k: int) -> list[VectorHit]:
        if self._index is None or self._index.ntotal == 0:
            return []
        q_vec = np.array([self._get_embedder().embed_query(text)], dtype="float32")
        scores, indices = self._index.search(q_vec, top_k)
        id_to_chunk = {v: k for k, v in self._chunk_id_to_faiss_id.items()}
        hits: list[VectorHit] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            chunk_id = id_to_chunk.get(int(idx))
            if not chunk_id:
                continue
            hits.append(VectorHit(chunk_id=chunk_id, score=float(score)))
        return hits
