from __future__ import annotations

from collections.abc import Iterable

import numpy as np


class NumpyVectorIndex:
    """Exact cosine retrieval used for tests and local fallback serving."""

    def __init__(self, item_ids: np.ndarray, embeddings: np.ndarray) -> None:
        if len(item_ids) != len(embeddings):
            raise ValueError("item_ids and embeddings must have the same length")
        self.item_ids = item_ids.astype("int64")
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        self.embeddings = embeddings / np.maximum(norms, 1e-12)

    def search(
        self, query: np.ndarray, k: int, excluded_item_ids: Iterable[int] = ()
    ) -> list[tuple[int, float]]:
        if k <= 0 or len(self.item_ids) == 0:
            return []
        query = query.astype("float32")
        query = query / max(float(np.linalg.norm(query)), 1e-12)
        scores = self.embeddings @ query
        excluded = set(map(int, excluded_item_ids))
        fetch = min(len(scores), k + len(excluded) + 100)
        indices = np.argpartition(-scores, fetch - 1)[:fetch]
        indices = indices[np.argsort(-scores[indices])]
        result = []
        for index in indices:
            item_id = int(self.item_ids[index])
            if item_id in excluded:
                continue
            result.append((item_id, float(scores[index])))
            if len(result) == k:
                break
        return result

