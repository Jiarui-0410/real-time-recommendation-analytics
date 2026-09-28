import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from retail_stream.api.engine import RecommendationEngine
from retail_stream.recommendation.baseline import PopularityRecommender
from retail_stream.recommendation.data import temporal_split
from retail_stream.recommendation.evaluate import ranking_metrics
from retail_stream.retrieval.local_index import NumpyVectorIndex


class RecommendationCoreTest(unittest.TestCase):
    def test_temporal_split_never_moves_future_into_train(self) -> None:
        frame = pd.DataFrame(
            {
                "event_time": pd.date_range("2026-01-01", periods=20, freq="h", tz="UTC"),
                "visitor_id": [1, 2] * 10,
                "item_id": range(20),
                "event_type": ["view"] * 20,
                "weight": [1.0] * 20,
            }
        )
        split = temporal_split(frame)
        self.assertLess(split.train["event_time"].max(), split.validation["event_time"].min())
        self.assertLess(split.validation["event_time"].max(), split.test["event_time"].min())

    def test_popularity_filters_seen_items(self) -> None:
        frame = pd.DataFrame({"item_id": [10, 10, 20], "weight": [1.0, 3.0, 1.0]})
        model = PopularityRecommender().fit(frame)
        self.assertEqual(model.recommend(1, 2, {10}), [20])

    def test_ranking_metrics(self) -> None:
        metrics = ranking_metrics(
            {1: [10, 20], 2: [30, 40]},
            {1: {20}, 2: {99}},
            k=2,
            catalog={10, 20, 30, 40, 99},
        )
        self.assertAlmostEqual(metrics["recall@2"], 0.5)
        self.assertAlmostEqual(metrics["hit_rate@2"], 0.5)
        self.assertEqual(metrics["evaluated_users"], 2)

    def test_numpy_index_excludes_seen_items(self) -> None:
        index = NumpyVectorIndex(
            np.array([10, 20, 30]),
            np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]], dtype="float32"),
        )
        result = index.search(np.array([1.0, 0.0], dtype="float32"), 2, {10})
        self.assertEqual([item for item, _ in result], [20, 30])

    def test_engine_uses_popularity_for_unknown_user(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            np.save(path / "user_ids.npy", np.array([1]))
            np.save(path / "user_embeddings.npy", np.array([[1.0, 0.0]], dtype="float32"))
            np.save(path / "item_ids.npy", np.array([10, 20]))
            np.save(path / "item_embeddings.npy", np.eye(2, dtype="float32"))
            (path / "seen_items.json").write_text(json.dumps({"1": [10]}), encoding="utf-8")
            (path / "popularity.json").write_text(
                json.dumps({"ranked_items": [20, 10], "scores": {"20": 5, "10": 2}}),
                encoding="utf-8",
            )
            engine = RecommendationEngine(path)
            result = engine.recommend(999, 1)
        self.assertEqual(result["strategy"], "popularity_cold_start")
        self.assertEqual(result["recommendations"][0]["item_id"], 20)

