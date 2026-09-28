from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


class PopularityRecommender:
    def __init__(self) -> None:
        self.ranked_items: list[int] = []
        self.scores: dict[int, float] = {}

    def fit(self, interactions: pd.DataFrame) -> PopularityRecommender:
        weights = interactions["weight"] if "weight" in interactions else 1.0
        scores = interactions.assign(_weight=weights).groupby("item_id")["_weight"].sum()
        scores = scores.sort_values(ascending=False, kind="stable")
        self.ranked_items = [int(item) for item in scores.index]
        self.scores = {int(item): float(score) for item, score in scores.items()}
        return self

    def recommend(self, user_id: int, k: int, seen_items: Iterable[int] = ()) -> list[int]:
        del user_id
        seen = set(seen_items)
        return [item for item in self.ranked_items if item not in seen][:k]

