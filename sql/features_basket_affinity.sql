DROP TABLE IF EXISTS feat_basket_affinity;

-- Step A: pick top products to keep compute reasonable in Postgres
CREATE TABLE feat_basket_affinity AS
WITH top_products AS (
  SELECT product_id
  FROM order_products_prior
  GROUP BY product_id
  ORDER BY COUNT(*) DESC
  LIMIT 5000
),
order_items AS (
  SELECT op.order_id, op.product_id
  FROM order_products_prior op
  JOIN top_products tp
    ON op.product_id = tp.product_id
),
pairs AS (
  SELECT
    a.product_id AS product_id_a,
    b.product_id AS product_id_b,
    COUNT(*) AS co_purchase_count
  FROM order_items a
  JOIN order_items b
    ON a.order_id = b.order_id
   AND a.product_id < b.product_id
  GROUP BY 1,2
)
SELECT
  product_id_a,
  product_id_b,
  co_purchase_count
FROM pairs
WHERE co_purchase_count >= 50;

CREATE INDEX IF NOT EXISTS idx_aff_a ON feat_basket_affinity(product_id_a);
CREATE INDEX IF NOT EXISTS idx_aff_b ON feat_basket_affinity(product_id_b);

