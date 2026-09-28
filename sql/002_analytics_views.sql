CREATE OR REPLACE VIEW user_daily_metrics AS
SELECT
    event_time::date AS metric_date,
    visitor_id,
    count(*) FILTER (WHERE event_type = 'view') AS views,
    count(*) FILTER (WHERE event_type = 'addtocart') AS cart_adds,
    count(*) FILTER (WHERE event_type = 'transaction') AS purchases,
    count(DISTINCT item_id) AS distinct_items
FROM fact_events
GROUP BY event_time::date, visitor_id;

CREATE OR REPLACE VIEW item_daily_metrics AS
SELECT
    event_time::date AS metric_date,
    item_id,
    max(category_id) AS category_id,
    count(*) FILTER (WHERE event_type = 'view') AS views,
    count(*) FILTER (WHERE event_type = 'addtocart') AS cart_adds,
    count(*) FILTER (WHERE event_type = 'transaction') AS purchases,
    count(DISTINCT visitor_id) AS unique_users
FROM fact_events
GROUP BY event_time::date, item_id;

CREATE OR REPLACE VIEW funnel_daily AS
WITH daily AS (
    SELECT
        event_time::date AS metric_date,
        count(DISTINCT visitor_id) FILTER (WHERE event_type = 'view') AS view_users,
        count(DISTINCT visitor_id) FILTER (WHERE event_type = 'addtocart') AS cart_users,
        count(DISTINCT visitor_id) FILTER (WHERE event_type = 'transaction') AS purchase_users
    FROM fact_events
    GROUP BY event_time::date
)
SELECT
    metric_date,
    view_users,
    cart_users,
    purchase_users,
    cart_users::numeric / NULLIF(view_users, 0) AS view_to_cart_rate,
    purchase_users::numeric / NULLIF(cart_users, 0) AS cart_to_purchase_rate,
    purchase_users::numeric / NULLIF(view_users, 0) AS view_to_purchase_rate
FROM daily;

