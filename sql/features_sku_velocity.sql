DROP TABLE IF EXISTS feat_sku_velocity;

CREATE TABLE feat_sku_velocity AS
WITH user_orders AS (
  SELECT
    user_id,
    order_id,
    order_number
  FROM orders
),
product_orders AS (
  SELECT
    uo.user_id,
    op.product_id,
    COUNT(*) AS times_bought,
    MAX(uo.order_number) AS last_order_number_bought
  FROM user_orders uo
  JOIN order_products_prior op
    ON uo.order_id = op.order_id
  GROUP BY 1,2
),
global_orders AS (
  SELECT
    product_id,
    COUNT(*) AS total_units,
    COUNT(DISTINCT order_id) AS total_orders,
    AVG(reordered::int) AS reorder_rate
  FROM order_products_prior
  GROUP BY 1
)
SELECT
  p.product_id,
  p.product_name,
  p.aisle_id,
  p.department_id,
  g.total_units,
  g.total_orders,
  g.reorder_rate
FROM products p
JOIN global_orders g
  ON p.product_id = g.product_id;

CREATE INDEX IF NOT EXISTS idx_feat_sku_velocity_product_id
ON feat_sku_velocity(product_id);
