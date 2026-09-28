from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("compact-clean-events")
    .config("spark.sql.session.timeZone", "UTC")
    .getOrCreate()
)

source = "/opt/project/data/processed/clean_events"
target = "/opt/project/data/processed/clean_events_compacted"

df = spark.read.parquet(source)

(
    df.repartition("event_date")
      .write
      .mode("overwrite")
      .partitionBy("event_date")
      .parquet(target)
)

print("Compaction completed successfully.")
spark.stop()
