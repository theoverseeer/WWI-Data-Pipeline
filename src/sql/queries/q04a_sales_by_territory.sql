-- Q4a: Sales and profit by sales territory.
SELECT
    ci.sales_territory,
    SUM(f.total_excluding_tax) AS sales_excluding_tax,
    SUM(f.profit) AS profit,
    ROUND(100.0 * SUM(f.profit) / SUM(f.total_excluding_tax), 2) AS profit_margin_pct
FROM asb_olap.fact_sale f
JOIN asb_olap.dim_city ci ON ci.city_key = f.city_key
GROUP BY ci.sales_territory
ORDER BY sales_excluding_tax DESC;
