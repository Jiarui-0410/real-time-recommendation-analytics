from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

DISPLAY_NAMES = {
    "popularity": "Popularity",
    "two_tower": "Two-Tower",
    "two_tower_with_fallback": "Two-Tower + fallback",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize saved recommendation evaluation metrics to PostgreSQL."
    )
    parser.add_argument(
        "--input",
        default="artifacts/model_full_v1/expanded_metrics.json",
        help="Expanded evaluation metrics JSON artifact.",
    )
    return parser.parse_args(argv)


def metric_rows(payload: dict) -> list[tuple[str, str, str, float, int]]:
    rows: list[tuple[str, str, str, float, int]] = []
    for cohort_key, cohort_name in (("overall", "Overall"), ("warm_users", "Warm users")):
        for model_key, values in payload[cohort_key].items():
            evaluated_users = int(values["evaluated_users"])
            model_name = DISPLAY_NAMES.get(model_key, model_key.replace("_", " ").title())
            for metric_name in (
                "recall@10",
                "hit_rate@10",
                "ndcg@10",
                "catalog_coverage@10",
            ):
                rows.append(
                    (
                        cohort_name,
                        model_name,
                        metric_name,
                        float(values[metric_name]),
                        evaluated_users,
                    )
                )
    return rows


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = Path(args.input)
    payload = json.loads(source.read_text(encoding="utf-8"))
    rows = metric_rows(payload)
    protocol = payload["protocol"]

    import psycopg

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://retail:retail_local_only@localhost:5432/retail_analytics",
    )
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute("TRUNCATE recommendation_evaluation_metrics")
        cursor.executemany(
            """
            INSERT INTO recommendation_evaluation_metrics (
                cohort, model_name, metric_name, metric_value, evaluated_users
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            rows,
        )
        cursor.execute(
            """
            INSERT INTO recommendation_evaluation_protocol (
                id, sampled_test_users, evaluated_users, warm_evaluated_users,
                cold_user_fallbacks, cold_start_item_interactions,
                recommendation_k, evaluation_seed, source_artifact, loaded_at
            ) VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (id) DO UPDATE SET
                sampled_test_users = EXCLUDED.sampled_test_users,
                evaluated_users = EXCLUDED.evaluated_users,
                warm_evaluated_users = EXCLUDED.warm_evaluated_users,
                cold_user_fallbacks = EXCLUDED.cold_user_fallbacks,
                cold_start_item_interactions = EXCLUDED.cold_start_item_interactions,
                recommendation_k = EXCLUDED.recommendation_k,
                evaluation_seed = EXCLUDED.evaluation_seed,
                source_artifact = EXCLUDED.source_artifact,
                loaded_at = now()
            """,
            (
                int(protocol["sampled_test_users"]),
                int(protocol["evaluated_users"]),
                int(protocol["warm_evaluated_users"]),
                int(protocol["cold_user_fallbacks"]),
                int(protocol["cold_start_item_interactions"]),
                int(protocol["k"]),
                int(protocol["seed"]),
                str(source.as_posix()),
            ),
        )

    print(f"Loaded {len(rows)} metric row(s) from {source} into PostgreSQL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
