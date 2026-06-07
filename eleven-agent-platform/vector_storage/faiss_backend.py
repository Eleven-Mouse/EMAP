from __future__ import annotations

import json
import pathlib

import numpy as np

from vector_storage.base import BackendQueryHit


class FaissVectorBackend:
    name = "faiss"

    def __init__(self, index_path: str, mapping_path: str) -> None:
        self.index_path = index_path
        self.mapping_path = mapping_path
        self._faiss = None
        self._index = None
        self._item_id_to_faiss_id: dict[str, int] = {}
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
            self._item_id_to_faiss_id = {
                str(k): int(v) for k, v in payload.get("item_id_to_faiss_id", {}).items()
            }
            self._next_faiss_id = int(payload.get("next_faiss_id", 1))
            return
        self._index = None

    def _persist(self) -> None:
        if self._index is None:
            return
        faiss = self._get_faiss()
        index_path = pathlib.Path(self.index_path)
        mapping_path = pathlib.Path(self.mapping_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(index_path))
        mapping_path.write_text(
            json.dumps(
                {
                    "item_id_to_faiss_id": self._item_id_to_faiss_id,
                    "next_faiss_id": self._next_faiss_id,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _allocate_faiss_id(self, item_id: str) -> int:
        existing = self._item_id_to_faiss_id.get(item_id)
        if existing is not None:
            return existing
        faiss_id = self._next_faiss_id
        self._next_faiss_id += 1
        self._item_id_to_faiss_id[item_id] = faiss_id
        return faiss_id

    def upsert(self, item_ids: list[str], vectors: np.ndarray) -> None:
        if not item_ids:
            return
        if self._index is None:
            self._index = self._make_index(vectors.shape[1])
        ids = np.array([self._allocate_faiss_id(item_id) for item_id in item_ids], dtype="int64")
        self._index.add_with_ids(vectors, ids)
        self._persist()

    def remove(self, item_ids: list[str]) -> None:
        if not item_ids or self._index is None:
            return
        ids = [
            self._item_id_to_faiss_id.pop(item_id)
            for item_id in item_ids
            if item_id in self._item_id_to_faiss_id
        ]
        if not ids:
            return
        self._index.remove_ids(np.array(ids, dtype="int64"))
        self._persist()

    def query(self, query_vector: np.ndarray, top_k: int) -> list[BackendQueryHit]:
        if self._index is None or self._index.ntotal == 0:
            return []
        scores, indices = self._index.search(query_vector, top_k)
        faiss_id_to_item_id = {value: key for key, value in self._item_id_to_faiss_id.items()}
        hits: list[BackendQueryHit] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            item_id = faiss_id_to_item_id.get(int(idx))
            if not item_id:
                continue
            hits.append(BackendQueryHit(item_id=item_id, score=float(score)))
        return hits
