# Design review and frozen MVP

## Verdict

The project is strong because Kafka, Spark, SQL, BI, model training, vector retrieval,
and serving form one coherent system. It should be presented as a data-and-ML platform,
not merely as a second recommender project.

## Corrections made before implementation

1. **Realtime claim.** Kafka ingestion and online vector search are realtime, but a
   periodically trained user tower is not. V1 therefore claims streaming analytics and
   online serving. A later milestone may add a rolling online user representation.
2. **Item metadata.** Retailrocket events do not directly contain `category_id`.
   Categories and properties must be derived from timestamped item-property files, with
   an as-of join to avoid future-data leakage.
3. **Idempotency.** Kafka and Spark can replay records. A deterministic `event_id` and a
   database primary key are required before writing streaming results.
4. **Sessionization.** A 30-minute session gap is easy in batch but stateful in streaming.
   It is not part of the first ingestion slice.
5. **Recommendation evaluation.** The test period, eligible items, seen-item filtering,
   cold-start policy, and negative/candidate sampling must all be stated with the score.
6. **Power BI.** The repository versions the PBIP/TMDL definition, screenshots, SQL
   datasets, and setup notes; local caches and credentials remain excluded.

## Frozen MVP order

1. Deterministic replay producer, event contract, local infrastructure, SQL schema.
2. Spark batch ETL and Structured Streaming with quarantine + idempotent sinks.
3. Popularity baseline and leakage-safe temporal dataset.
4. PyTorch Two-Tower, offline evaluation, item indexing in Qdrant.
5. FastAPI endpoints and latency/health metrics.
6. Power BI dashboard, private Blob artifacts, then Azure VM deployment.

Cloud deployment is deliberately last: deploying an unverified local pipeline adds cost but not
technical credibility.

