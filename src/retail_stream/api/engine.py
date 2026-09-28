from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from retail_stream.retrieval.local_index import NumpyVectorIndex


class RecommendationEngine:
    def __init__(self, model_dir: str | Path, vector_index=None) -> None:
        model_dir = Path(model_dir)
        self.user_ids = np.load(model_dir / "user_ids.npy")
        self.user_embeddings = np.load(model_dir / "user_embeddings.npy")
        self.item_ids = np.load(model_dir / "item_ids.npy")
        self.item_embeddings = np.load(model_dir / "item_embeddings.npy")
        self.user_to_index = {int(user_id): index for index, user_id in enumerate(self.user_ids)}
        self.seen_items = {
            int(user_id): set(map(int, items))
            for user_id, items in json.loads((model_dir / "seen_items.json").read_text()).items()
        }
        popularity = json.loads((model_dir / "popularity.json").read_text())
        self.popular_items = list(map(int, popularity["ranked_items"]))
        self.popularity_scores = {int(k): float(v) for k, v in popularity["scores"].items()}
        self.vector_index = vector_index or NumpyVectorIndex(self.item_ids, self.item_embeddings)

    def recommend(self, user_id: int, k: int = 10, filter_seen: bool = True) -> dict:
        if not 1 <= k <= 100:
            raise ValueError("k must be between 1 and 100")
        seen = self.seen_items.get(user_id, set()) if filter_seen else set()
        user_index = self.user_to_index.get(user_id)
        if user_index is None:
            ranked = [item for item in self.popular_items if item not in seen][:k]
            recommendations = [
                {"item_id": item, "score": self.popularity_scores.get(item, 0.0)} for item in ranked
            ]
            strategy = "popularity_cold_start"
        else:
            matches = self.vector_index.search(self.user_embeddings[user_index], k, seen)
            recommendations = [{"item_id": item, "score": score} for item, score in matches]
            strategy = "two_tower_retrieval"
        return {
            "user_id": user_id,
            "strategy": strategy,
            "filter_seen": filter_seen,
            "recommendations": recommendations,
        }

