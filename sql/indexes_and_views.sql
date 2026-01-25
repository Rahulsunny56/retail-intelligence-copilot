-- Performance indexes (huge speedup)
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id);

CREATE INDEX IF NOT EXISTS idx_op_prior_order_id ON order_products_prior(order_id);
CREATE INDEX IF NOT EXISTS idx_op_prior_product_id ON order_products_prior(product_id);

CREATE INDEX IF NOT EXISTS idx_op_train_order_id ON order_products_train(order_id);
CREATE INDEX IF NOT EXISTS idx_op_train_product_id ON order_products_train(product_id);

CREATE INDEX IF NOT EXISTS idx_products_product_id ON products(product_id);

-- Analytics-ready view for AI + feature engineering
CREATE OR REPLACE VIEW v_order_products AS
SELECT
    o.order_id,
    o.user_id,
    o.order_number,
    o.order_dow,
    o.order_hour_of_day,
    o.days_since_prior_order,
    p.product_id,
    p.product_name,
    p.aisle_id,
    p.department_id,
    op.add_to_cart_order,
    op.reordered
FROM orders o
JOIN order_products_prior op
  ON o.order_id = op.order_id
JOIN products p
  ON op.product_id = p.product_id;
