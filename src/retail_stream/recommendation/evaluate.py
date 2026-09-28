from __future__ import annotations

import math
from collections.abc import Callable, Iterable

import pandas as pd


def ranking_metrics(
    recommendations: dict[int, list[int]],
    relevant: dict[int, set[int]],
    *,
    k: int,
    catalog: Iterable[int],
) -> dict[str, float | int]:
    recalls: list[float] = []
    hits: list[float] = []
    ndcgs: list[float] = []
    recommended_items: set[int] = set()
    for user_id, truth in relevant.items():
        if not truth:
            continue
        ranked = recommendations.get(user_id, [])[:k]
        recommended_items.update(ranked)
        hit_positions = [rank for rank, item in enumerate(ranked) if item in truth]
        recalls.append(len(hit_positions) / len(truth))
        hits.append(float(bool(hit_positions)))
        dcg = sum(1 / math.log2(rank + 2) for rank in hit_positions)
        ideal_hits = min(len(truth), k)
        idcg = sum(1 / math.log2(rank + 2) for rank in range(ideal_hits))
        ndcgs.append(dcg / idcg if idcg else 0.0)
    catalog_set = set(catalog)
    return {
        f"recall@{k}": sum(recalls) / len(recalls) if recalls else 0.0,
        f"hit_rate@{k}": sum(hits) / len(hits) if hits else 0.0,
        f"ndcg@{k}": sum(ndcgs) / len(ndcgs) if ndcgs else 0.0,
        f"catalog_coverage@{k}": len(recommended_items) / len(catalog_set) if catalog_set else 0.0,
        "evaluated_users": len(recalls),
    }


def evaluate_recommender(
    train: pd.DataFrame,
    test: pd.DataFrame,
    recommend: Callable[[int, int, set[int]], list[int]],
    *,
    k: int = 10,
    filter_seen: bool = True,
) -> dict[str, float | int]:
    catalog = set(int(item) for item in train["item_id"].unique())
    seen_by_user = train.groupby("visitor_id")["item_id"].agg(lambda values: set(map(int, values)))
    truth: dict[int, set[int]] = {}
    cold_start_interactions = 0
    for user_id, group in test.groupby("visitor_id"):
        eligible = set(map(int, group["item_id"])) & catalog
        cold_start_interactions += len(group) - len(group[group["item_id"].isin(catalog)])
        if filter_seen:
            eligible -= seen_by_user.get(user_id, set())
        if eligible:
            truth[int(user_id)] = eligible
    recommendations = {
        user_id: recommend(user_id, k, seen_by_user.get(user_id, set()) if filter_seen else set())
        for user_id in truth
    }
    metrics = ranking_metrics(recommendations, truth, k=k, catalog=catalog)
    metrics["cold_start_test_interactions"] = cold_start_interactions
    return metrics

