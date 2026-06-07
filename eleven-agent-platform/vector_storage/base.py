from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass
class BackendQueryHit:
    item_id: str
    score: float


class VectorBackend(Protocol):
    name: str

    def upsert(self, item_ids: list[str], vectors: np.ndarray) -> None:
        ...

    def remove(self, item_ids: list[str]) -> None:
        ...

    def query(self, query_vector: np.ndarray, top_k: int) -> list[BackendQueryHit]:
        ...
