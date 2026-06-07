from __future__ import annotations

import numpy as np

from vector_storage.base import BackendQueryHit


class MemoryVectorBackend:
    name = "memory"

    def __init__(self) -> None:
        self._vectors: dict[str, np.ndarray] = {}

    def upsert(self, item_ids: list[str], vectors: np.ndarray) -> None:
        for item_id, vector in zip(item_ids, vectors, strict=True):
            self._vectors[item_id] = np.array(vector, dtype="float32")

    def remove(self, item_ids: list[str]) -> None:
        for item_id in item_ids:
            self._vectors.pop(item_id, None)

    def query(self, query_vector: np.ndarray, top_k: int) -> list[BackendQueryHit]:
        if not self._vectors:
            return []
        base_vector = np.array(query_vector[0], dtype="float32")
        hits = [
            BackendQueryHit(item_id=item_id, score=float(np.dot(base_vector, vector)))
            for item_id, vector in self._vectors.items()
        ]
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]
