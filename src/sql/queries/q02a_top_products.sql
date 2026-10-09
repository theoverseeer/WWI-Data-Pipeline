-- Q2a: Top 20 products by sales, with profit and both rankings.
SELECT
    s.stock_item_name,
    s.brand,
    s.color_name,
    SUM(f.quantity) AS quantity_sold,
    SUM(f.total_excluding_tax) AS sales_excluding_tax,
    SUM(f.profit) AS profit,
    RANK() OVER (ORDER BY SUM(f.total_excluding_tax) DESC) AS sales_rank,
    RANK() OVER (ORDER BY SUM(f.profit) DESC) AS profit_rank
FROM asb_olap.fact_sale f
JOIN asb_olap.dim_stock_item s ON s.stock_item_key = f.stock_item_key
GROUP BY s.stock_item_name, s.brand, s.color_name
ORDER BY sales_rank
LIMIT 20;
