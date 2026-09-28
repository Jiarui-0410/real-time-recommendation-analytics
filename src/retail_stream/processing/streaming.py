from __future__ import annotations

import argparse
import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StreamingConfig:
    bootstrap_servers: str
    topic: str
    parquet_path: str
    checkpoint_path: str
    quarantine_path: str
    jdbc_url: str
    database_url: str
    postgres_user: str
    postgres_password: str
    watermark: str = "10 minutes"


def event_schema():
    from pyspark.sql.types import LongType, StringType, StructField, StructType

    return StructType(
        [
            StructField("event_id", StringType(), True),
            StructField("source_timestamp_ms", LongType(), True),
            StructField("occurred_at", StringType(), True),
            StructField("visitor_id", LongType(), True),
            StructField("item_id", LongType(), True),
            StructField("event_type", StringType(), True),
            StructField("transaction_id", StringType(), True),
            StructField("source", StringType(), True),
            StructField("schema_version", LongType(), True),
        ]
    )


def parse_kafka_events(kafka_df, watermark: str = "10 minutes"):
    from pyspark.sql import functions as F

    parsed = kafka_df.select(
        F.col("topic"),
        F.col("partition"),
        F.col("offset"),
        F.col("timestamp").alias("kafka_timestamp"),
        F.col("value").cast("string").alias("raw_value"),
        F.from_json(F.col("value").cast("string"), event_schema()).alias("payload"),
    ).select("*", "payload.*").drop("payload")

    required_missing = (
        F.col("event_id").isNull()
        | F.col("source_timestamp_ms").isNull()
        | F.col("visitor_id").isNull()
        | F.col("item_id").isNull()
        | F.col("event_type").isNull()
        | F.col("source").isNull()
        | F.col("schema_version").isNull()
    )
    bad_type = ~F.col("event_type").isin("view", "addtocart", "transaction")
    bad_identifier = (
        (F.col("visitor_id") < 0)
        | (F.col("item_id") < 0)
        | (F.col("source_timestamp_ms") < 0)
    )
    bad_event_id = ~F.col("event_id").rlike(r"^[0-9a-f]{64}$")
    bad_schema = F.col("schema_version") != 1
    bad_time = F.to_timestamp("occurred_at").isNull()
    invalid_condition = (
        required_missing
        | bad_type
        | bad_identifier
        | bad_event_id
        | bad_schema
        | bad_time
    )

    invalid = parsed.filter(invalid_condition).select(
        "topic",
        "partition",
        "offset",
        "raw_value",
        F.when(required_missing, "missing_required_field")
        .when(bad_type, "unsupported_event_type")
        .when(bad_identifier, "negative_identifier")
        .when(bad_event_id, "invalid_event_id")
        .when(bad_schema, "unsupported_schema_version")
        .otherwise("invalid_occurred_at")
        .alias("error_reason"),
    )

    valid = (
        parsed.filter(~invalid_condition)
        .withColumn("event_time", F.to_timestamp("occurred_at"))
        .withWatermark("event_time", watermark)
        .dropDuplicatesWithinWatermark(["event_id"])
        .select(
            "event_id",
            "source_timestamp_ms",
            "event_time",
            "visitor_id",
            "item_id",
            "event_type",
            "transaction_id",
            "source",
            F.col("schema_version").cast("short").alias("schema_version"),
        )
    )
    return valid, invalid


def _batch_completed(
    database_url: str, batch_id: int, pipeline_name: str = "user_events_stream"
) -> bool:
    import psycopg

    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM pipeline_runs WHERE pipeline_name = %s AND batch_id = %s",
            (pipeline_name, batch_id),
        )
        return cursor.fetchone() is not None


def _prepare_stage(database_url: str, batch_id: int) -> None:
    import psycopg

    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM staging_events WHERE ingest_batch_id = %s", (batch_id,))


def _commit_stage(
    database_url: str,
    batch_id: int,
    row_count: int,
    pipeline_name: str = "user_events_stream",
) -> None:
    import psycopg

    statement = """
        INSERT INTO fact_events (
            event_id, source_timestamp_ms, event_time, visitor_id, item_id,
            event_type, transaction_id, category_id, session_id, source, schema_version
        )
        SELECT event_id, source_timestamp_ms, event_time, visitor_id, item_id,
               event_type, transaction_id, category_id, session_id, source, schema_version
        FROM staging_events
        WHERE ingest_batch_id = %s
        ON CONFLICT (event_id) DO NOTHING
    """
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(statement, (batch_id,))
        cursor.execute(
            """
            INSERT INTO pipeline_runs (pipeline_name, batch_id, row_count)
            VALUES (%s, %s, %s)
            ON CONFLICT (pipeline_name, batch_id) DO NOTHING
            """,
            (pipeline_name, batch_id, row_count),
        )
        cursor.execute("DELETE FROM staging_events WHERE ingest_batch_id = %s", (batch_id,))


def make_valid_batch_writer(config: StreamingConfig):
    def write_batch(batch_df, batch_id: int) -> None:
        from pyspark.sql import functions as F

        if _batch_completed(config.database_url, batch_id):
            return

        batch_df.persist()
        try:
            row_count = batch_df.count()
            if row_count == 0:
                return
            batch_path = f"{config.parquet_path}/batch_id={batch_id}"
            batch_df.write.mode("overwrite").parquet(batch_path)

            _prepare_stage(config.database_url, batch_id)
            staged = (
                batch_df.withColumn("ingest_batch_id", F.lit(batch_id))
                .withColumn("category_id", F.lit(None).cast("long"))
                .withColumn("session_id", F.lit(None).cast("string"))
            )
            staged.select(
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
            ).write.format("jdbc").option("url", config.jdbc_url).option(
                "dbtable", "staging_events"
            ).option("user", config.postgres_user).option(
                "password", config.postgres_password
            ).option("driver", "org.postgresql.Driver").mode("append").save()
            _commit_stage(config.database_url, batch_id, row_count)
        finally:
            batch_df.unpersist()

    return write_batch


def start_queries(spark, config: StreamingConfig):
    kafka = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", config.bootstrap_servers)
        .option("subscribe", config.topic)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .load()
    )
    valid, invalid = parse_kafka_events(kafka, config.watermark)
    valid_query = (
        valid.writeStream.foreachBatch(make_valid_batch_writer(config))
        .option("checkpointLocation", f"{config.checkpoint_path}/valid")
        .queryName("valid-user-events")
        .start()
    )
    invalid_query = (
        invalid.writeStream.format("parquet")
        .option("path", config.quarantine_path)
        .option("checkpointLocation", f"{config.checkpoint_path}/invalid")
        .outputMode("append")
        .queryName("invalid-user-events")
        .start()
    )
    return valid_query, invalid_query


def config_from_env() -> StreamingConfig:
    return StreamingConfig(
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        topic=os.getenv("KAFKA_TOPIC", "user_events"),
        parquet_path=os.getenv("PROCESSED_DATA_PATH", "data/processed/streaming_events"),
        checkpoint_path=os.getenv("CHECKPOINT_PATH", "checkpoints/user_events"),
        quarantine_path=os.getenv("QUARANTINE_PATH", "data/processed/quarantine"),
        jdbc_url=os.getenv("JDBC_URL", "jdbc:postgresql://localhost:5432/retail_analytics"),
        database_url=os.getenv(
            "DATABASE_URL", "postgresql://retail:retail_local_only@localhost:5432/retail_analytics"
        ),
        postgres_user=os.getenv("POSTGRES_USER", "retail"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", "retail_local_only"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consume and validate retail events")
    parser.parse_args(argv)
    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder.appName("retail-event-stream")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    queries = start_queries(spark, config_from_env())
    try:
        spark.streams.awaitAnyTermination()
    finally:
        for query in queries:
            query.stop()
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
