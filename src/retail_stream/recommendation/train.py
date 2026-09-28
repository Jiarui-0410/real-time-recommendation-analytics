from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from retail_stream.recommendation.baseline import PopularityRecommender
from retail_stream.recommendation.data import load_clean_events, temporal_split
from retail_stream.recommendation.evaluate import evaluate_recommender


def _standardize(values: np.ndarray) -> np.ndarray:
    values = values.astype("float32")
    scale = float(values.std()) or 1.0
    return (values - float(values.mean())) / scale


def build_features(train: pd.DataFrame):
    user_ids = np.sort(train["visitor_id"].unique().astype("int64"))
    item_ids = np.sort(train["item_id"].unique().astype("int64"))
    categories = np.sort(train["category_id"].fillna(-1).unique().astype("int64"))
    user_to_index = {int(value): index for index, value in enumerate(user_ids)}
    item_to_index = {int(value): index for index, value in enumerate(item_ids)}
    category_to_index = {int(value): index for index, value in enumerate(categories)}

    user_counts = (
        train.pivot_table(
            index="visitor_id",
            columns="event_type",
            values="item_id",
            aggfunc="count",
            fill_value=0,
        )
        .reindex(index=user_ids, columns=["view", "addtocart", "transaction"], fill_value=0)
        .to_numpy(dtype="float32")
    )
    user_features = np.log1p(user_counts)
    for column in range(user_features.shape[1]):
        user_features[:, column] = _standardize(user_features[:, column])

    item_groups = train.groupby("item_id")
    counts = item_groups.size().reindex(item_ids, fill_value=0).to_numpy()
    unique_users = (
        item_groups["visitor_id"].nunique().reindex(item_ids, fill_value=0).to_numpy()
    )
    item_features = np.column_stack(
        (_standardize(np.log1p(counts)), _standardize(np.log1p(unique_users)))
    )
    latest_categories = (
        train.sort_values("event_time")
        .groupby("item_id")["category_id"]
        .last()
        .reindex(item_ids)
        .fillna(-1)
    )
    item_category_indices = np.array(
        [category_to_index[int(value)] for value in latest_categories], dtype="int64"
    )
    return {
        "user_ids": user_ids,
        "item_ids": item_ids,
        "categories": categories,
        "user_to_index": user_to_index,
        "item_to_index": item_to_index,
        "user_features": user_features.astype("float32"),
        "item_features": item_features.astype("float32"),
        "item_category_indices": item_category_indices,
    }


def train_model(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    features: dict,
    *,
    embedding_dim: int,
    hidden_dim: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    seed: int,
    patience: int,
):
    import torch
    from torch.nn import functional as F
    from torch.utils.data import DataLoader, Dataset

    from retail_stream.recommendation.two_tower import TwoTower

    torch.manual_seed(seed)
    np.random.seed(seed)
    def indexed(frame: pd.DataFrame):
        indexed_frame = frame.assign(
            _user_index=frame["visitor_id"].map(features["user_to_index"]),
            _item_index=frame["item_id"].map(features["item_to_index"]),
        ).dropna(subset=["_user_index", "_item_index"])
        return (
            indexed_frame["_user_index"].to_numpy(dtype="int64"),
            indexed_frame["_item_index"].to_numpy(dtype="int64"),
            indexed_frame["weight"].to_numpy(dtype="float32"),
        )

    train_users, train_items, train_weights = indexed(train)
    validation_users, validation_items, validation_weights = indexed(validation)
    train_seen: dict[int, set[int]] = {}
    for user_index, item_index in zip(train_users, train_items, strict=True):
        train_seen.setdefault(int(user_index), set()).add(int(item_index))

    class PairwiseDataset(Dataset):
        def __init__(self, users, items, weights, seed_offset: int = 0):
            self.users = users
            self.items = items
            self.weights = weights
            self.seed_offset = seed_offset
            self.positions = np.array(
                [
                    index
                    for index, (user, positive) in enumerate(zip(users, items, strict=True))
                    if len(train_seen.get(int(user), set()) | {int(positive)})
                    < len(features["item_ids"])
                ],
                dtype="int64",
            )

        def __len__(self):
            return len(self.positions)

        def __getitem__(self, index):
            source_index = int(self.positions[index])
            user_index = int(self.users[source_index])
            positive = int(self.items[source_index])
            blocked = train_seen.get(user_index, set()) | {positive}
            negative = (
                source_index * 9973 + seed + self.seed_offset
            ) % len(features["item_ids"])
            while negative in blocked:
                negative = (negative + 1) % len(features["item_ids"])
            return user_index, positive, negative, self.weights[source_index]

    train_dataset = PairwiseDataset(train_users, train_items, train_weights)
    if len(train_dataset) == 0:
        raise ValueError(
            "negative sampling requires at least one unseen item for a training user"
        )
    validation_dataset = PairwiseDataset(
        validation_users, validation_items, validation_weights, seed_offset=1_000_003
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = TwoTower(
        len(features["user_ids"]),
        len(features["item_ids"]),
        len(features["categories"]),
        embedding_dim,
        hidden_dim,
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=1e-5
    )
    loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, num_workers=0
    )
    validation_loader = (
        DataLoader(validation_dataset, batch_size=batch_size, shuffle=False, num_workers=0)
        if len(validation_dataset)
        else None
    )
    user_feature_tensor = torch.tensor(features["user_features"], device=device)
    item_feature_tensor = torch.tensor(features["item_features"], device=device)
    item_category_tensor = torch.tensor(features["item_category_indices"], device=device)
    history = []
    best_state = None
    best_monitor = float("inf")
    epochs_without_improvement = 0

    def batch_loss(users, positives, negatives, batch_weights):
        users = users.to(device)
        positives = positives.to(device)
        negatives = negatives.to(device)
        batch_weights = batch_weights.to(device)
        positive_scores, negative_scores = model(
            users,
            user_feature_tensor[users],
            positives,
            item_category_tensor[positives],
            item_feature_tensor[positives],
            negatives,
            item_category_tensor[negatives],
            item_feature_tensor[negatives],
        )
        per_example = F.softplus(-(positive_scores - negative_scores))
        return (per_example * batch_weights).sum() / batch_weights.sum(), len(users)

    for epoch in range(epochs):
        model.train()
        loss_sum = 0.0
        example_count = 0
        for batch_index, (users, positives, negatives, batch_weights) in enumerate(
            loader, start=1
        ):
            loss, examples = batch_loss(users, positives, negatives, batch_weights)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            loss_sum += float(loss.detach()) * examples
            example_count += examples
            if batch_index % 100 == 0 or batch_index == len(loader):
                running_loss = loss_sum / max(example_count, 1)
                print(
                    f"epoch={epoch + 1} batch={batch_index}/{len(loader)} "
                    f"running_train_loss={running_loss:.6f}"
                )
        epoch_loss = loss_sum / max(example_count, 1)

        validation_loss = None
        if validation_loader is not None:
            model.eval()
            validation_sum = 0.0
            validation_count = 0
            with torch.no_grad():
                for batch in validation_loader:
                    loss, examples = batch_loss(*batch)
                    validation_sum += float(loss) * examples
                    validation_count += examples
            validation_loss = validation_sum / max(validation_count, 1)

        monitor = validation_loss if validation_loss is not None else epoch_loss
        history.append(
            {
                "epoch": epoch + 1,
                "train_loss": epoch_loss,
                "validation_loss": validation_loss,
            }
        )
        print(
            f"epoch={epoch + 1} train_loss={epoch_loss:.6f} "
            f"validation_loss={validation_loss if validation_loss is not None else 'n/a'}"
        )
        if monitor < best_monitor:
            best_monitor = monitor
            best_state = {
                name: parameter.detach().cpu().clone()
                for name, parameter in model.state_dict().items()
            }
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if validation_loader is not None and epochs_without_improvement >= patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    model.eval()
    with torch.no_grad():
        user_embeddings = model.encode_user(
            torch.arange(len(features["user_ids"]), device=device), user_feature_tensor
        ).cpu().numpy()
        item_embeddings = model.encode_item(
            torch.arange(len(features["item_ids"]), device=device),
            item_category_tensor,
            item_feature_tensor,
        ).cpu().numpy()
    return model, user_embeddings, item_embeddings, history, device


def save_artifacts(
    output_dir: Path,
    model,
    features: dict,
    user_embeddings: np.ndarray,
    item_embeddings: np.ndarray,
    train: pd.DataFrame,
    popularity: PopularityRecommender,
    config: dict,
    metrics: dict,
    history: list[dict],
) -> None:
    import torch

    output_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_dir / "two_tower.pt")
    np.save(output_dir / "user_ids.npy", features["user_ids"])
    np.save(output_dir / "item_ids.npy", features["item_ids"])
    np.save(output_dir / "categories.npy", features["categories"])
    np.save(output_dir / "user_features.npy", features["user_features"])
    np.save(output_dir / "item_features.npy", features["item_features"])
    np.save(
        output_dir / "item_category_indices.npy", features["item_category_indices"]
    )
    np.save(output_dir / "user_embeddings.npy", user_embeddings.astype("float32"))
    np.save(output_dir / "item_embeddings.npy", item_embeddings.astype("float32"))
    seen = {
        str(int(user_id)): sorted(map(int, group["item_id"].unique()))
        for user_id, group in train.groupby("visitor_id")
    }
    (output_dir / "seen_items.json").write_text(json.dumps(seen), encoding="utf-8")
    (output_dir / "popularity.json").write_text(
        json.dumps({"ranked_items": popularity.ranked_items, "scores": popularity.scores}),
        encoding="utf-8",
    )
    (output_dir / "model_config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (output_dir / "training_history.json").write_text(
        json.dumps(history, indent=2), encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Train and evaluate a PyTorch Two-Tower model"
    )
    parser.add_argument("input", help="clean event Parquet directory or CSV")
    parser.add_argument("--output-dir", default="artifacts/model")
    parser.add_argument("--embedding-dim", type=int, default=64)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--patience", type=int, default=2)
    parser.add_argument("--evaluation-k", type=int, default=10)
    parser.add_argument("--max-evaluation-users", type=int, default=5000)
    args = parser.parse_args(argv)

    events = load_clean_events(args.input)
    split = temporal_split(events)
    test = split.test
    test_users = np.sort(test["visitor_id"].unique())
    if len(test_users) > args.max_evaluation_users:
        rng = np.random.default_rng(args.seed)
        selected_users = rng.choice(
            test_users, size=args.max_evaluation_users, replace=False
        )
        test = test[test["visitor_id"].isin(selected_users)].copy()
    features = build_features(split.train)
    popularity = PopularityRecommender().fit(split.train)
    baseline_metrics = evaluate_recommender(
        split.train, test, popularity.recommend, k=args.evaluation_k
    )
    model, user_embeddings, item_embeddings, history, device = train_model(
        split.train,
        split.validation,
        features,
        embedding_dim=args.embedding_dim,
        hidden_dim=args.hidden_dim,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        seed=args.seed,
        patience=args.patience,
    )

    user_id_to_index = features["user_to_index"]
    item_ids = features["item_ids"]

    def model_recommend(user_id: int, k: int, seen_items: set[int]) -> list[int]:
        index = user_id_to_index.get(user_id)
        if index is None:
            return popularity.recommend(user_id, k, seen_items)
        scores = item_embeddings @ user_embeddings[index]
        limit = min(len(scores), k + len(seen_items) + 100)
        candidates = np.argpartition(-scores, limit - 1)[:limit]
        candidates = candidates[np.argsort(-scores[candidates])]
        return [int(item_ids[i]) for i in candidates if int(item_ids[i]) not in seen_items][:k]

    model_metrics = evaluate_recommender(
        split.train, test, model_recommend, k=args.evaluation_k
    )
    metrics = {"popularity": baseline_metrics, "two_tower": model_metrics}
    config = {
        "embedding_dim": args.embedding_dim,
        "hidden_dim": args.hidden_dim,
        "num_users": len(features["user_ids"]),
        "num_items": len(features["item_ids"]),
        "num_categories": len(features["categories"]),
        "train_end": split.train_end,
        "validation_end": split.validation_end,
        "device": str(device),
        "loss": "weighted_pairwise_bpr",
        "early_stopping_patience": args.patience,
        "best_epoch": min(history, key=lambda row: row["validation_loss"])["epoch"]
        if history and history[0]["validation_loss"] is not None
        else len(history),
    }
    save_artifacts(
        Path(args.output_dir),
        model,
        features,
        user_embeddings,
        item_embeddings,
        split.train,
        popularity,
        config,
        metrics,
        history,
    )
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
