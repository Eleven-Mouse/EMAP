from __future__ import annotations

import hashlib

import numpy as np

from vector_storage.base import BackendQueryHit


class QdrantVectorBackend:
    name = "qdrant"

    def __init__(self, url: str, collection_name: str) -> None:
        self.url = url
        self.collection_name = collection_name
        self._client = None
        self._collection_ensured = False

    def _get_client(self):
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError as exc:
                raise RuntimeError(
                    "qdrant-client is required when VECTOR_BACKEND=qdrant."
                ) from exc
            self._client = QdrantClient(url=self.url)
        return self._client

    @staticmethod
    def _point_id(item_id: str) -> int:
        digest = hashlib.sha256(item_id.encode("utf-8")).hexdigest()[:16]
        return int(digest, 16)

    def upsert(self, item_ids: list[str], vectors: np.ndarray) -> None:
        if not item_ids:
            return
        client = self._get_client()
        try:
            from qdrant_client.http import models as qmodels
        except ImportError as exc:
            raise RuntimeError(
                "qdrant-client models are unavailable when VECTOR_BACKEND=qdrant."
            ) from exc
        if not self._collection_ensured:
            vector_size = int(vectors.shape[1])
            try:
                client.get_collection(self.collection_name)
            except Exception:
                client.recreate_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=vector_size,
                        distance=qmodels.Distance.COSINE,
                    ),
                )
            self._collection_ensured = True
        client.upsert(
            collection_name=self.collection_name,
            points=[
                qmodels.PointStruct(
                    id=self._point_id(item_id),
                    vector=vector.tolist(),
                    payload={"item_id": item_id},
                )
                for item_id, vector in zip(item_ids, vectors, strict=True)
            ],
        )

    def remove(self, item_ids: list[str]) -> None:
        if not item_ids:
            return
        client = self._get_client()
        client.delete(
            collection_name=self.collection_name,
            points_selector=[self._point_id(item_id) for item_id in item_ids],
        )

    def query(self, query_vector: np.ndarray, top_k: int) -> list[BackendQueryHit]:
        client = self._get_client()
        results = client.search(
            collection_name=self.collection_name,
            query_vector=query_vector[0].tolist(),
            limit=top_k,
        )
        return [
            BackendQueryHit(
                item_id=str(result.payload.get("item_id", "")),
                score=float(result.score),
            )
            for result in results
            if result.payload.get("item_id")
        ]
