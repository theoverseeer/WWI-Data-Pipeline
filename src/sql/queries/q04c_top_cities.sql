-- Q4c: Top 25 cities by sales (with state and territory).
SELECT
    ci.city_name,
    ci.state_province_name,
    ci.sales_territory,
    SUM(f.total_excluding_tax) AS sales_excluding_tax,
    SUM(f.profit) AS profit
FROM asb_olap.fact_sale f
JOIN asb_olap.dim_city ci ON ci.city_key = f.city_key
GROUP BY ci.city_name, ci.state_province_name, ci.sales_territory
ORDER BY sales_excluding_tax DESC
LIMIT 25;
