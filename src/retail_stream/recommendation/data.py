from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

EVENT_WEIGHTS = {"view": 1.0, "addtocart": 3.0, "transaction": 5.0}
REQUIRED_COLUMNS = {"visitor_id", "item_id", "event_type", "event_time"}


@dataclass(frozen=True, slots=True)
class TemporalSplit:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    train_end: str
    validation_end: str


def load_clean_events(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
    else:
        frame = pd.read_parquet(path)
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"clean events missing columns: {', '.join(sorted(missing))}")
    frame = frame.copy()
    frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True, errors="raise")
    frame["event_type"] = frame["event_type"].str.lower()
    frame = frame[frame["event_type"].isin(EVENT_WEIGHTS)].copy()
    frame["weight"] = frame["event_type"].map(EVENT_WEIGHTS).astype("float32")
    if "category_id" not in frame:
        frame["category_id"] = -1
    frame["category_id"] = frame["category_id"].fillna(-1).astype("int64")
    return frame.sort_values(["event_time", "visitor_id", "item_id"]).reset_index(
        drop=True
    )


def temporal_split(
    events: pd.DataFrame, train_fraction: float = 0.8, validation_fraction: float = 0.1
) -> TemporalSplit:
    if events.empty:
        raise ValueError("cannot split an empty event table")
    if not 0 < train_fraction < 1 or not 0 <= validation_fraction < 1:
        raise ValueError("fractions must be between zero and one")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("train_fraction + validation_fraction must be below one")
    ordered = events.sort_values("event_time").reset_index(drop=True)
    train_end_idx = max(1, int(len(ordered) * train_fraction))
    validation_end_idx = max(
        train_end_idx + 1,
        int(len(ordered) * (train_fraction + validation_fraction)),
    )
    validation_end_idx = min(validation_end_idx, len(ordered))
    train = ordered.iloc[:train_end_idx].copy()
    validation = ordered.iloc[train_end_idx:validation_end_idx].copy()
    test = ordered.iloc[validation_end_idx:].copy()
    return TemporalSplit(
        train=train,
        validation=validation,
        test=test,
        train_end=train["event_time"].max().isoformat(),
        validation_end=(
            validation["event_time"].max()
            if not validation.empty
            else train["event_time"].max()
        ).isoformat(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create leakage-safe recommendation splits")
    parser.add_argument("input")
    parser.add_argument("--output-dir", default="data/processed/training")
    args = parser.parse_args(argv)
    events = load_clean_events(args.input)
    split = temporal_split(events)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    split.train.to_parquet(output / "train.parquet", index=False)
    split.validation.to_parquet(output / "validation.parquet", index=False)
    split.test.to_parquet(output / "test.parquet", index=False)
    metadata = {
        "rows": {
            "train": len(split.train),
            "validation": len(split.validation),
            "test": len(split.test),
        },
        "train_end": split.train_end,
        "validation_end": split.validation_end,
        "event_weights": EVENT_WEIGHTS,
    }
    (output / "split_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
