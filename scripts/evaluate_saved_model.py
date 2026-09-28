from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from retail_stream.recommendation.data import load_clean_events, temporal_split
from retail_stream.recommendation.evaluate import ranking_metrics


def build_truth(
    train: pd.DataFrame,
    test: pd.DataFrame,
    catalog: set[int],
) -> tuple[dict[int, set[int]], dict[int, set[int]], int]:
    selected_users = set(map(int, test["visitor_id"].unique()))
    selected_train = train[train["visitor_id"].isin(selected_users)]
    seen_by_user = {
        int(user_id): set(map(int, group["item_id"]))
        for user_id, group in selected_train.groupby("visitor_id")
    }
    truth: dict[int, set[int]] = {}
    cold_start_item_interactions = 0
    for user_id, group in test.groupby("visitor_id"):
        items = set(map(int, group["item_id"]))
        eligible = items & catalog
        cold_start_item_interactions += len(group) - int(group["item_id"].isin(catalog).sum())
        eligible -= seen_by_user.get(int(user_id), set())
        if eligible:
            truth[int(user_id)] = eligible
    return truth, seen_by_user, cold_start_item_interactions


def popularity_recommendations(
    users: list[int],
    ranked_items: list[int],
    seen_by_user: dict[int, set[int]],
    k: int,
) -> dict[int, list[int]]:
    recommendations = {}
    for user_id in users:
        seen = seen_by_user.get(user_id, set())
        recommendations[user_id] = [item for item in ranked_items if item not in seen][:k]
    return recommendations


def two_tower_recommendations(
    users: list[int],
    user_to_index: dict[int, int],
    user_embeddings: np.ndarray,
    item_ids: np.ndarray,
    item_embeddings: np.ndarray,
    ranked_items: list[int],
    seen_by_user: dict[int, set[int]],
    k: int,
    batch_size: int,
) -> tuple[dict[int, list[int]], int]:
    item_to_index = {int(item_id): index for index, item_id in enumerate(item_ids)}
    recommendations: dict[int, list[int]] = {}
    warm_users = [user_id for user_id in users if user_id in user_to_index]
    cold_users = [user_id for user_id in users if user_id not in user_to_index]

    for user_id in cold_users:
        seen = seen_by_user.get(user_id, set())
        recommendations[user_id] = [item for item in ranked_items if item not in seen][:k]

    item_matrix = np.asarray(item_embeddings, dtype="float32")
    for start in range(0, len(warm_users), batch_size):
        batch_users = warm_users[start : start + batch_size]
        batch_indices = np.array([user_to_index[user_id] for user_id in batch_users])
        scores = np.asarray(user_embeddings[batch_indices], dtype="float32") @ item_matrix.T
        for row, user_id in enumerate(batch_users):
            seen_indices = [
                item_to_index[item_id]
                for item_id in seen_by_user.get(user_id, set())
                if item_id in item_to_index
            ]
            if seen_indices:
                scores[row, seen_indices] = -np.inf
            candidate_indices = np.argpartition(-scores[row], k - 1)[:k]
            candidate_indices = candidate_indices[np.argsort(-scores[row, candidate_indices])]
            recommendations[user_id] = [int(item_ids[index]) for index in candidate_indices]
        completed = min(start + batch_size, len(warm_users))
        if completed % 500 < batch_size or completed == len(warm_users):
            print(f"evaluated {completed}/{len(warm_users)} warm user(s)")
    return recommendations, len(warm_users)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate saved Two-Tower embeddings")
    parser.add_argument("input", help="clean event Parquet directory")
    parser.add_argument("--model-dir", default="artifacts/model_full_v1")
    parser.add_argument("--max-users", type=int, default=5000)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.max_users < 1 or args.k < 1 or args.batch_size < 1:
        raise ValueError("max-users, k, and batch-size must be positive")

    model_dir = Path(args.model_dir)
    print("loading and temporally splitting clean events...")
    split = temporal_split(load_clean_events(args.input))
    test_users = np.sort(split.test["visitor_id"].unique().astype("int64"))
    if len(test_users) > args.max_users:
        rng = np.random.default_rng(args.seed)
        test_users = rng.choice(test_users, size=args.max_users, replace=False)
    selected_test = split.test[split.test["visitor_id"].isin(test_users)].copy()

    user_ids = np.load(model_dir / "user_ids.npy", mmap_mode="r")
    item_ids = np.load(model_dir / "item_ids.npy", mmap_mode="r")
    user_embeddings = np.load(model_dir / "user_embeddings.npy", mmap_mode="r")
    item_embeddings = np.load(model_dir / "item_embeddings.npy", mmap_mode="r")
    user_to_index = {int(user_id): index for index, user_id in enumerate(user_ids)}
    catalog = set(map(int, item_ids))
    popularity = json.loads((model_dir / "popularity.json").read_text(encoding="utf-8"))
    ranked_items = list(map(int, popularity["ranked_items"]))

    truth, seen_by_user, cold_item_interactions = build_truth(
        split.train, selected_test, catalog
    )
    evaluated_users = sorted(truth)
    popularity_recs = popularity_recommendations(
        evaluated_users, ranked_items, seen_by_user, args.k
    )
    two_tower_recs, warm_count = two_tower_recommendations(
        evaluated_users,
        user_to_index,
        user_embeddings,
        item_ids,
        item_embeddings,
        ranked_items,
        seen_by_user,
        args.k,
        args.batch_size,
    )
    warm_truth = {user_id: truth[user_id] for user_id in truth if user_id in user_to_index}

    result = {
        "protocol": {
            "sampled_test_users": int(len(test_users)),
            "evaluated_users": len(truth),
            "warm_evaluated_users": warm_count,
            "cold_user_fallbacks": len(truth) - warm_count,
            "cold_start_item_interactions": cold_item_interactions,
            "k": args.k,
            "seed": args.seed,
        },
        "overall": {
            "popularity": ranking_metrics(
                popularity_recs, truth, k=args.k, catalog=catalog
            ),
            "two_tower_with_fallback": ranking_metrics(
                two_tower_recs, truth, k=args.k, catalog=catalog
            ),
        },
        "warm_users": {
            "popularity": ranking_metrics(
                popularity_recs, warm_truth, k=args.k, catalog=catalog
            ),
            "two_tower": ranking_metrics(
                two_tower_recs, warm_truth, k=args.k, catalog=catalog
            ),
        },
    }
    output = Path(args.output) if args.output else model_dir / "expanded_metrics.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"saved expanded evaluation to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
