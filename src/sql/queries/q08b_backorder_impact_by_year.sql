-- Q8b: Business impact of backorders by fiscal year, plus a total row.
SELECT
    COALESCE(d.fiscal_year_label, 'All years') AS fiscal_year,
    COUNT(DISTINCT f.order_id) AS orders,
    COUNT(DISTINCT CASE WHEN f.is_backordered THEN f.order_id END) AS orders_with_backorders,
    COUNT(*) FILTER (WHERE f.is_backordered) AS backordered_lines,
    SUM(f.backordered_quantity) AS backordered_quantity,
    SUM(f.backordered_amount_excluding_tax) AS unfulfilled_value_excluding_tax,
    ROUND(100.0 * SUM(f.backordered_amount_excluding_tax) / SUM(f.total_excluding_tax), 2) AS pct_of_ordered_value
FROM asb_olap.fact_order f
JOIN asb_olap.dim_date d ON d.date_key = f.order_date_key
GROUP BY ROLLUP (d.fiscal_year_label)
ORDER BY d.fiscal_year_label NULLS LAST;
