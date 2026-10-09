-- Q10: Which dimension version did each transaction use? For customers with more than one version,
-- sales before and after the change, and a check that every invoice date sits inside its version's date range.
SELECT
    c.customer_id,
    c.customer_name,
    c.customer_category_name,
    c.buying_group_name,
    c.delivery_city_name,
    c.effective_start_date,
    c.effective_end_date,
    COUNT(DISTINCT f.invoice_id) AS invoices,
    MIN(d.full_date) AS first_invoice_date,
    MAX(d.full_date) AS last_invoice_date,
    SUM(f.total_including_tax) AS sales_including_tax,
    (MIN(d.full_date) >= c.effective_start_date AND MAX(d.full_date) <= c.effective_end_date) AS all_invoices_inside_version_range
FROM asb_olap.fact_sale f
JOIN asb_olap.dim_customer c ON c.customer_key = f.customer_key
JOIN asb_olap.dim_date d ON d.date_key = f.invoice_date_key
WHERE c.customer_id IN (
    SELECT customer_id FROM asb_olap.dim_customer WHERE customer_id IS NOT NULL GROUP BY customer_id HAVING COUNT(*) > 1)
GROUP BY c.customer_id, c.customer_name, c.customer_category_name, c.buying_group_name,
         c.delivery_city_name, c.effective_start_date, c.effective_end_date
ORDER BY c.customer_id, c.effective_start_date;
