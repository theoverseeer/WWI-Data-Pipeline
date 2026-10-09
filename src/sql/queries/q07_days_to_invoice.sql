-- Q7: Average days from order to invoice (and invoice to delivery), per invoice, by fiscal year plus a total row.
WITH inv AS (
    SELECT invoice_id, invoice_date_key,
           MIN(days_order_to_invoice) AS days_to_invoice,
           MIN(days_invoice_to_delivery) AS days_to_delivery
    FROM asb_olap.fact_sale
    GROUP BY invoice_id, invoice_date_key
)
SELECT
    COALESCE(d.fiscal_year_label, 'All years') AS fiscal_year,
    COUNT(*) AS invoices,
    ROUND(AVG(inv.days_to_invoice), 2) AS avg_days_order_to_invoice,
    MIN(inv.days_to_invoice) AS min_days,
    MAX(inv.days_to_invoice) AS max_days,
    ROUND(AVG(inv.days_to_delivery), 2) AS avg_days_invoice_to_delivery
FROM inv
JOIN asb_olap.dim_date d ON d.date_key = inv.invoice_date_key
GROUP BY ROLLUP (d.fiscal_year_label)
ORDER BY d.fiscal_year_label NULLS LAST;
