CREATE OR REPLACE VIEW dashboard_fact_events AS
SELECT
    event_time::date AS event_date,
    extract(hour FROM event_time)::smallint AS event_hour,
    visitor_id,
    item_id,
    category_id,
    event_type,
    source
FROM fact_events;

CREATE OR REPLACE VIEW dashboard_calendar AS
SELECT
    calendar_date::date AS calendar_date,
    extract(year FROM calendar_date)::integer AS calendar_year,
    extract(month FROM calendar_date)::integer AS calendar_month_number,
    to_char(calendar_date, 'Mon') AS calendar_month,
    extract(isodow FROM calendar_date)::integer AS day_of_week_number,
    trim(to_char(calendar_date, 'Day')) AS day_of_week
FROM generate_series(
    (SELECT min(event_time)::date FROM fact_events),
    (SELECT max(event_time)::date FROM fact_events),
    interval '1 day'
) AS calendar_date;

CREATE TABLE IF NOT EXISTS dashboard_top_items_data (
    purchase_rank integer PRIMARY KEY,
    item_id text NOT NULL,
    category_id text,
    views bigint NOT NULL,
    cart_adds bigint NOT NULL,
    purchases bigint NOT NULL,
    unique_users bigint NOT NULL,
    view_to_purchase_rate numeric
);
TRUNCATE dashboard_top_items_data;
INSERT INTO dashboard_top_items_data
WITH item_metrics AS (
    SELECT
        item_id,
        max(category_id) AS category_id,
        count(*) FILTER (WHERE event_type = 'view') AS views,
        count(*) FILTER (WHERE event_type = 'addtocart') AS cart_adds,
        count(*) FILTER (WHERE event_type = 'transaction') AS purchases,
        count(DISTINCT visitor_id) AS unique_users,
        count(*) FILTER (WHERE event_type = 'transaction')::numeric
            / NULLIF(count(*) FILTER (WHERE event_type = 'view'), 0)
            AS view_to_purchase_rate
    FROM fact_events
    GROUP BY item_id
), ranked AS (
    SELECT
        row_number() OVER (
            ORDER BY purchases DESC, views DESC, item_id
        )::integer AS purchase_rank,
        item_id,
        category_id,
        views,
        cart_adds,
        purchases,
        unique_users,
        view_to_purchase_rate
    FROM item_metrics
    WHERE purchases > 0
)
SELECT
    purchase_rank,
    lpad(purchase_rank::text, 2, '0') || '. Item ' || item_id::text,
    CASE
        WHEN category_id IS NULL THEN NULL
        ELSE 'Category ' || category_id::text
    END,
    views,
    cart_adds,
    purchases,
    unique_users,
    view_to_purchase_rate
FROM ranked
WHERE purchase_rank <= 20
ORDER BY purchase_rank;

CREATE OR REPLACE VIEW dashboard_top_items AS
SELECT * FROM dashboard_top_items_data;

CREATE TABLE IF NOT EXISTS dashboard_top_categories_data (
    purchase_rank integer PRIMARY KEY,
    category_id text NOT NULL,
    views bigint NOT NULL,
    cart_adds bigint NOT NULL,
    purchases bigint NOT NULL,
    unique_users bigint NOT NULL,
    distinct_items bigint NOT NULL
);
TRUNCATE dashboard_top_categories_data;
INSERT INTO dashboard_top_categories_data
WITH category_metrics AS (
    SELECT
        category_id,
        count(*) FILTER (WHERE event_type = 'view') AS views,
        count(*) FILTER (WHERE event_type = 'addtocart') AS cart_adds,
        count(*) FILTER (WHERE event_type = 'transaction') AS purchases,
        count(DISTINCT visitor_id) AS unique_users,
        count(DISTINCT item_id) AS distinct_items
    FROM fact_events
    WHERE category_id IS NOT NULL
    GROUP BY category_id
), ranked AS (
    SELECT
        row_number() OVER (
            ORDER BY purchases DESC, views DESC, category_id
        )::integer AS purchase_rank,
        category_id,
        views,
        cart_adds,
        purchases,
        unique_users,
        distinct_items
    FROM category_metrics
    WHERE purchases > 0
)
SELECT
    purchase_rank,
    lpad(purchase_rank::text, 2, '0') || '. Category ' || category_id::text,
    views,
    cart_adds,
    purchases,
    unique_users,
    distinct_items
FROM ranked
WHERE purchase_rank <= 15
ORDER BY purchase_rank;

CREATE OR REPLACE VIEW dashboard_top_categories AS
SELECT * FROM dashboard_top_categories_data;

CREATE TABLE IF NOT EXISTS dashboard_user_activity_data (
    activity_bucket text NOT NULL,
    bucket_order integer PRIMARY KEY,
    user_count bigint NOT NULL
);
TRUNCATE dashboard_user_activity_data;
INSERT INTO dashboard_user_activity_data
WITH user_totals AS (
    SELECT visitor_id, count(*) AS event_count
    FROM fact_events
    GROUP BY visitor_id
), bucketed AS (
    SELECT
        CASE
            WHEN event_count = 1 THEN '1 event'
            WHEN event_count BETWEEN 2 AND 5 THEN '2-5 events'
            WHEN event_count BETWEEN 6 AND 10 THEN '6-10 events'
            WHEN event_count BETWEEN 11 AND 25 THEN '11-25 events'
            WHEN event_count BETWEEN 26 AND 50 THEN '26-50 events'
            ELSE '51+ events'
        END AS activity_bucket,
        CASE
            WHEN event_count = 1 THEN 1
            WHEN event_count BETWEEN 2 AND 5 THEN 2
            WHEN event_count BETWEEN 6 AND 10 THEN 3
            WHEN event_count BETWEEN 11 AND 25 THEN 4
            WHEN event_count BETWEEN 26 AND 50 THEN 5
            ELSE 6
        END AS bucket_order
    FROM user_totals
)
SELECT activity_bucket, bucket_order, count(*) AS user_count
FROM bucketed
GROUP BY activity_bucket, bucket_order;

CREATE OR REPLACE VIEW dashboard_user_activity_distribution AS
SELECT * FROM dashboard_user_activity_data;

CREATE TABLE IF NOT EXISTS dashboard_funnel_stages_data (
    stage_order integer PRIMARY KEY,
    stage text NOT NULL,
    users bigint NOT NULL
);
TRUNCATE dashboard_funnel_stages_data;
INSERT INTO dashboard_funnel_stages_data
SELECT 1 AS stage_order, '1. View users' AS stage,
       count(DISTINCT visitor_id) FILTER (WHERE event_type = 'view') AS users
FROM fact_events
UNION ALL
SELECT 2, '2. Cart users',
       count(DISTINCT visitor_id) FILTER (WHERE event_type = 'addtocart')
FROM fact_events
UNION ALL
SELECT 3, '3. Purchase users',
       count(DISTINCT visitor_id) FILTER (WHERE event_type = 'transaction')
FROM fact_events;

CREATE OR REPLACE VIEW dashboard_funnel_stages AS
SELECT * FROM dashboard_funnel_stages_data;

CREATE TABLE IF NOT EXISTS recommendation_evaluation_metrics (
    cohort          text NOT NULL,
    model_name      text NOT NULL,
    metric_name     text NOT NULL,
    metric_value    double precision NOT NULL,
    evaluated_users integer NOT NULL,
    PRIMARY KEY (cohort, model_name, metric_name)
);

CREATE TABLE IF NOT EXISTS recommendation_evaluation_protocol (
    id                           smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    sampled_test_users           integer NOT NULL,
    evaluated_users              integer NOT NULL,
    warm_evaluated_users         integer NOT NULL,
    cold_user_fallbacks          integer NOT NULL,
    cold_start_item_interactions integer NOT NULL,
    recommendation_k             integer NOT NULL,
    evaluation_seed              integer NOT NULL,
    source_artifact              text NOT NULL,
    loaded_at                    timestamptz NOT NULL DEFAULT now()
);

