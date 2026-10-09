-- Q3a: Top 20 customers by revenue (all versions of a customer are combined by business key).
SELECT
    c.customer_id,
    c.customer_name,
    COUNT(DISTINCT f.invoice_id) AS invoices,
    SUM(f.total_excluding_tax) AS sales_excluding_tax,
    SUM(f.profit) AS profit,
    RANK() OVER (ORDER BY SUM(f.total_excluding_tax) DESC) AS sales_rank
FROM asb_olap.fact_sale f
JOIN asb_olap.dim_customer c ON c.customer_key = f.customer_key
GROUP BY c.customer_id, c.customer_name
ORDER BY sales_rank
LIMIT 20;
