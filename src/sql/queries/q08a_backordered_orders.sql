-- Q8a: The 50 orders with the largest value of backordered (short-picked, never invoiced) items.
SELECT
    f.order_id,
    d.full_date AS order_date,
    c.customer_name,
    MAX(f.backorder_order_id) AS backorder_order_id,
    COUNT(*) FILTER (WHERE f.is_backordered) AS backordered_lines,
    SUM(f.backordered_quantity) AS backordered_quantity,
    SUM(f.backordered_amount_excluding_tax) AS unfulfilled_value_excluding_tax,
    SUM(f.total_excluding_tax) AS order_value_excluding_tax,
    ROUND(100.0 * SUM(f.backordered_amount_excluding_tax) / SUM(f.total_excluding_tax), 2) AS pct_of_order_value
FROM asb_olap.fact_order f
JOIN asb_olap.dim_date d ON d.date_key = f.order_date_key
JOIN asb_olap.dim_customer c ON c.customer_key = f.customer_key
GROUP BY f.order_id, d.full_date, c.customer_name
HAVING SUM(f.backordered_quantity) > 0
ORDER BY unfulfilled_value_excluding_tax DESC
LIMIT 50;
