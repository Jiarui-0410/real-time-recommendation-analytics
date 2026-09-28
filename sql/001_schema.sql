CREATE TABLE IF NOT EXISTS fact_events (
    event_id            text PRIMARY KEY CHECK (event_id ~ '^[0-9a-f]{64}$'),
    source_timestamp_ms bigint NOT NULL CHECK (source_timestamp_ms >= 0),
    event_time          timestamptz NOT NULL,
    visitor_id          bigint NOT NULL CHECK (visitor_id >= 0),
    item_id             bigint NOT NULL CHECK (item_id >= 0),
    event_type          text NOT NULL CHECK (event_type IN ('view', 'addtocart', 'transaction')),
    transaction_id      text,
    category_id         bigint,
    session_id          text,
    source              text NOT NULL DEFAULT 'retailrocket_replay',
    schema_version      smallint NOT NULL DEFAULT 1,
    ingested_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fact_events_event_time ON fact_events (event_time);
CREATE INDEX IF NOT EXISTS idx_fact_events_visitor_time ON fact_events (visitor_id, event_time);
CREATE INDEX IF NOT EXISTS idx_fact_events_item_time ON fact_events (item_id, event_time);

-- Retailrocket item properties are timestamped. Keeping history allows an as-of
-- join and avoids leaking a future category/property into an older interaction.
CREATE TABLE IF NOT EXISTS item_property_history (
    item_id       bigint NOT NULL,
    property_name text NOT NULL,
    property_value text,
    observed_at   timestamptz NOT NULL,
    PRIMARY KEY (item_id, property_name, observed_at)
);

CREATE TABLE IF NOT EXISTS category_tree (
    category_id        bigint PRIMARY KEY,
    parent_category_id bigint REFERENCES category_tree (category_id)
);

CREATE TABLE IF NOT EXISTS streaming_dead_letter (
    kafka_topic     text NOT NULL,
    kafka_partition integer NOT NULL,
    kafka_offset    bigint NOT NULL,
    raw_value       text,
    error_reason    text NOT NULL,
    quarantined_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (kafka_topic, kafka_partition, kafka_offset)
);

-- Spark writes micro-batches here first. A driver-side transaction then moves
-- rows into fact_events with ON CONFLICT DO NOTHING and clears the batch.
CREATE TABLE IF NOT EXISTS staging_events (
    ingest_batch_id     bigint NOT NULL,
    event_id            text NOT NULL,
    source_timestamp_ms bigint NOT NULL,
    event_time          timestamptz NOT NULL,
    visitor_id          bigint NOT NULL,
    item_id             bigint NOT NULL,
    event_type          text NOT NULL,
    transaction_id      text,
    category_id         bigint,
    session_id          text,
    source              text NOT NULL,
    schema_version      smallint NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_staging_events_batch ON staging_events (ingest_batch_id);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    pipeline_name text NOT NULL,
    batch_id      bigint NOT NULL,
    row_count     bigint NOT NULL,
    completed_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (pipeline_name, batch_id)
);
