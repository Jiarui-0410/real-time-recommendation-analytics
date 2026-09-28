from __future__ import annotations

import argparse
import os
from pathlib import Path


def build_clean_events(spark, raw_dir: str, output_path: str, session_gap_minutes: int = 30):
    """Build leakage-safe clean events from the four Retailrocket CSV files."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F
    from pyspark.sql.types import LongType, StringType, StructField, StructType

    raw = Path(raw_dir)
    event_schema = StructType(
        [
            StructField("timestamp", LongType(), False),
            StructField("visitorid", LongType(), False),
            StructField("event", StringType(), False),
            StructField("itemid", LongType(), False),
            StructField("transactionid", StringType(), True),
        ]
    )
    property_schema = StructType(
        [
            StructField("timestamp", LongType(), False),
            StructField("itemid", LongType(), False),
            StructField("property", StringType(), False),
            StructField("value", StringType(), True),
        ]
    )

    events = (
        spark.read.option("header", True)
        .schema(event_schema)
        .csv(str(raw / "events.csv"))
        .filter(F.col("event").isin("view", "addtocart", "transaction"))
        .dropna(subset=["timestamp", "visitorid", "itemid", "event"])
        .withColumn(
            "event_id",
            F.sha2(
                F.concat_ws(
                    "|",
                    F.col("timestamp"),
                    F.col("visitorid"),
                    F.col("event"),
                    F.col("itemid"),
                    F.coalesce(F.col("transactionid"), F.lit("")),
                ),
                256,
            ),
        )
        .dropDuplicates(["event_id"])
    )

    properties = (
        spark.read.option("header", True)
        .schema(property_schema)
        .csv(
            [
                str(raw / "item_properties_part1.csv"),
                str(raw / "item_properties_part2.csv"),
            ]
        )
        .filter(F.col("property") == "categoryid")
        .filter(F.col("value").rlike(r"^[0-9]+$"))
        .select(
            "itemid",
            F.col("timestamp").alias("valid_from_ms"),
            F.col("value").cast("long").alias("category_id"),
        )
        .dropDuplicates(["itemid", "valid_from_ms"])
    )

    validity = Window.partitionBy("itemid").orderBy("valid_from_ms")
    category_intervals = properties.withColumn(
        "valid_to_ms", F.lead("valid_from_ms").over(validity)
    )

    e = events.alias("e")
    p = category_intervals.alias("p")
    joined = e.join(
        p,
        (F.col("e.itemid") == F.col("p.itemid"))
        & (F.col("e.timestamp") >= F.col("p.valid_from_ms"))
        & (F.col("p.valid_to_ms").isNull() | (F.col("e.timestamp") < F.col("p.valid_to_ms"))),
        "left",
    ).select("e.*", F.col("p.category_id"))

    user_time = Window.partitionBy("visitorid").orderBy("timestamp", "event_id")
    session_accumulator = user_time.rowsBetween(Window.unboundedPreceding, Window.currentRow)
    gap_ms = session_gap_minutes * 60 * 1000
    previous_time = F.lag("timestamp").over(user_time)
    session_start = F.when(
        previous_time.isNull() | ((F.col("timestamp") - previous_time) > gap_ms), 1
    ).otherwise(0)

    clean = (
        joined.withColumn("session_number", F.sum(session_start).over(session_accumulator))
        .withColumn("session_id", F.concat_ws("-", F.col("visitorid"), F.col("session_number")))
        .withColumn("event_time", F.to_timestamp(F.from_unixtime(F.col("timestamp") / 1000)))
        .withColumn("event_date", F.to_date("event_time"))
        .withColumn("day_of_week", F.dayofweek("event_time"))
        .withColumn("hour", F.hour("event_time"))
        .select(
            "event_id",
            F.col("timestamp").alias("source_timestamp_ms"),
            "event_time",
            F.col("visitorid").alias("visitor_id"),
            F.col("itemid").alias("item_id"),
            F.col("event").alias("event_type"),
            F.col("transactionid").alias("transaction_id"),
            "category_id",
            "session_id",
            "day_of_week",
            "hour",
            "event_date",
        )
    )
    clean.write.mode("overwrite").partitionBy("event_date").parquet(output_path)
    return clean


def load_historical_postgres(
    clean,
    jdbc_url: str,
    database_url: str,
    postgres_user: str,
    postgres_password: str,
) -> int:
    from pyspark.sql import functions as F

    from retail_stream.processing.streaming import _commit_stage, _prepare_stage

    batch_id = -1
    row_count = clean.count()
    _prepare_stage(database_url, batch_id)
    staged = (
        clean.withColumn("ingest_batch_id", F.lit(batch_id))
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
    )
    staged.write.format("jdbc").option("url", jdbc_url).option(
        "dbtable", "staging_events"
    ).option("user", postgres_user).option("password", postgres_password).option(
        "driver", "org.postgresql.Driver"
    ).mode("append").save()
    _commit_stage(database_url, batch_id, row_count, "historical_batch_load")
    return row_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build clean Retailrocket Parquet tables")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--output", default="data/processed/clean_events")
    parser.add_argument("--session-gap-minutes", type=int, default=30)
    parser.add_argument("--load-postgres", action="store_true")
    args = parser.parse_args(argv)

    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder.appName("retailrocket-batch-etl")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    try:
        clean = build_clean_events(spark, args.raw_dir, args.output, args.session_gap_minutes)
        row_count = clean.count()
        print(f"wrote {row_count} clean event(s) to {args.output}")
        if args.load_postgres:
            loaded = load_historical_postgres(
                clean,
                os.getenv("JDBC_URL", "jdbc:postgresql://localhost:5432/retail_analytics"),
                os.getenv(
                    "DATABASE_URL",
                    "postgresql://retail:retail_local_only@localhost:5432/retail_analytics",
                ),
                os.getenv("POSTGRES_USER", "retail"),
                os.getenv("POSTGRES_PASSWORD", "retail_local_only"),
            )
            print(f"loaded {loaded} historical event(s) into PostgreSQL")
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
