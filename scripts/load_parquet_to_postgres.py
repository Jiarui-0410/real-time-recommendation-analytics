from __future__ import annotations

import argparse
import os

REQUIRED_COLUMNS = {
    "event_id",
    "source_timestamp_ms",
    "event_time",
    "visitor_id",
    "item_id",
    "event_type",
    "transaction_id",
    "category_id",
    "session_id",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load existing clean-event Parquet into PostgreSQL without rerunning ETL."
    )
    parser.add_argument(
        "--input",
        default="data/processed/clean_events_compacted",
        help="Path to the existing compacted clean-event Parquet dataset.",
    )
    parser.add_argument(
        "--jdbc-partitions",
        type=int,
        default=8,
        help="Maximum number of concurrent JDBC writer partitions.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10_000,
        help="JDBC insert batch size per writer partition.",
    )
    args = parser.parse_args(argv)
    if args.jdbc_partitions < 1:
        parser.error("--jdbc-partitions must be at least 1")
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    from retail_stream.processing.streaming import _commit_stage, _prepare_stage

    jdbc_url = os.getenv(
        "JDBC_URL", "jdbc:postgresql://localhost:5432/retail_analytics"
    )
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://retail:retail_local_only@localhost:5432/retail_analytics",
    )
    postgres_user = os.getenv("POSTGRES_USER", "retail")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "retail_local_only")

    spark = (
        SparkSession.builder.appName("load-existing-parquet-to-postgres")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    try:
        clean = spark.read.parquet(args.input)
        missing = sorted(REQUIRED_COLUMNS.difference(clean.columns))
        if missing:
            raise ValueError(
                "Parquet dataset is missing required column(s): " + ", ".join(missing)
            )

        staged = (
            clean.select(*sorted(REQUIRED_COLUMNS))
            .withColumn("ingest_batch_id", F.lit(-1).cast("long"))
            .withColumn("source", F.lit("retailrocket_batch"))
            .withColumn("schema_version", F.lit(1).cast("short"))
            .select(
                "ingest_batch_id",
                "event_id",
                "source_timestamp_ms",
                "event_time",
                "visitor_id",
                "item_id",
                "event_type",
                "transaction_id",
                "category_id",
                "session_id",
                "source",
                "schema_version",
            )
            .repartition(args.jdbc_partitions)
        )

        staged.persist()
        try:
            row_count = staged.count()
            if row_count == 0:
                print(f"No rows found in {args.input}; PostgreSQL was not changed.")
                return 0

            print(
                f"Loading {row_count:,} existing Parquet row(s) into PostgreSQL "
                f"with {args.jdbc_partitions} JDBC partition(s)..."
            )
            _prepare_stage(database_url, -1)
            (
                staged.write.format("jdbc")
                .option("url", jdbc_url)
                .option("dbtable", "staging_events")
                .option("user", postgres_user)
                .option("password", postgres_password)
                .option("driver", "org.postgresql.Driver")
                .option("batchsize", args.batch_size)
                .option("numPartitions", args.jdbc_partitions)
                .mode("append")
                .save()
            )
            _commit_stage(
                database_url,
                batch_id=-1,
                row_count=row_count,
                pipeline_name="historical_batch_load",
            )
            print(
                f"PostgreSQL load complete for {row_count:,} source row(s). "
                "Existing event_id values were safely skipped."
            )
        finally:
            staged.unpersist()
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
