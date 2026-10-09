-- Q2b: Sales and profit by product category (stock group).
-- An item can be in several groups, so group totals add up to more than the overall total.
SELECT
    b.stock_group_name AS product_category,
    SUM(f.quantity) AS quantity_sold,
    SUM(f.total_excluding_tax) AS sales_excluding_tax,
    SUM(f.profit) AS profit,
    RANK() OVER (ORDER BY SUM(f.total_excluding_tax) DESC) AS sales_rank,
    RANK() OVER (ORDER BY SUM(f.profit) DESC) AS profit_rank
FROM asb_olap.fact_sale f
JOIN asb_olap.bridge_stock_item_group b ON b.stock_item_key = f.stock_item_key
GROUP BY b.stock_group_name
ORDER BY sales_rank;
