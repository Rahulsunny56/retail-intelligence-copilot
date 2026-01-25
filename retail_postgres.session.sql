--SELECT * FROM feat_basket_affinity limit 10;
--SELECT COUNT(*) FROM feat_sku_velocity;
SELECT product_id, product_name
FROM products
WHERE product_name ILIKE '%banana%'
ORDER BY LENGTH(product_name) ASC
LIMIT 20;
