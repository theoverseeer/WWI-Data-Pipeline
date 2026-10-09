-- Q3b: Revenue by customer category. The category is the one valid on the invoice date (SCD Type 2).
SELECT
    c.customer_category_name,
    COUNT(DISTINCT f.invoice_id) AS invoices,
    SUM(f.total_excluding_tax) AS sales_excluding_tax,
    SUM(f.profit) AS profit,
    ROUND(100.0 * SUM(f.total_excluding_tax) / SUM(SUM(f.total_excluding_tax)) OVER (), 2) AS pct_of_sales
FROM asb_olap.fact_sale f
JOIN asb_olap.dim_customer c ON c.customer_key = f.customer_key
GROUP BY c.customer_category_name
ORDER BY sales_excluding_tax DESC;
