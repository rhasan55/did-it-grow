-- The grain is market x week x product. Eligibility is fixed BEFORE launch.
-- Keep never-purchasers via the spine, and attribute refunds to purchase week.
-- In a warehouse, partition the source by order_week, cluster by market_id,
-- and MERGE corrections by order_id. Never incrementally SUM an append-only
-- correction feed without replacing the prior version.
CREATE OR REPLACE TABLE current_orders AS
SELECT * EXCLUDE (rn) FROM (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY order_id ORDER BY version DESC, ingested_at DESC
  ) AS rn FROM orders_raw
) WHERE rn = 1;

CREATE OR REPLACE TABLE market_week AS
WITH revenue AS (
  SELECT market_id, order_week AS week,
    SUM(CASE WHEN product = 'new_offer' THEN amount_cents-refund_cents ELSE 0 END)/100.0 AS new_revenue,
    SUM(CASE WHEN product = 'existing' THEN amount_cents-refund_cents ELSE 0 END)/100.0 AS existing_revenue,
    SUM(amount_cents-refund_cents)/100.0 AS total_revenue
  FROM current_orders GROUP BY 1,2
), spine AS (
  SELECT m.*, w.range AS week FROM markets m CROSS JOIN range(40) w
)
SELECT s.*, COALESCE(new_revenue,0) AS new_revenue,
  COALESCE(existing_revenue,0) AS existing_revenue,
  COALESCE(total_revenue,0) AS total_revenue,
  COALESCE(total_revenue,0)/eligible_at_baseline AS revenue_per_eligible
FROM spine s LEFT JOIN revenue r USING(market_id,week);
