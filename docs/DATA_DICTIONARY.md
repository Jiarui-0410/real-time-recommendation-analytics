# Data dictionary

## Kafka `user_events` contract

| Field | Type | Meaning |
|---|---|---|
| `event_id` | SHA-256 string | Deterministic idempotency key |
| `source_timestamp_ms` | integer | Original Retailrocket UTC epoch milliseconds |
| `occurred_at` | ISO-8601 string | UTC event time |
| `visitor_id` | integer | Anonymous user identifier |
| `item_id` | integer | Product identifier |
| `event_type` | enum | `view`, `addtocart`, or `transaction` |
| `transaction_id` | nullable string | Transaction identifier when supplied |
| `source` | string | Event provenance |
| `schema_version` | integer | Contract version, currently `1` |

## `fact_events`

One validated event per row. `event_id` is the primary key. `category_id` is nullable
because an item may lack category metadata at the event timestamp. `session_id` is
created by batch ETL; the first streaming milestone leaves it null.

## Item property history

Retailrocket properties are time-varying. Batch ETL converts category observations into
validity intervals and joins the latest category known **at** the event timestamp.

