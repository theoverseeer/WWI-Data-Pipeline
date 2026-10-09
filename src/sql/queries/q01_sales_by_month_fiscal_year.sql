-- Q1: Total sales, quantity sold and profit by month and fiscal year (fiscal year starts 1 November).
SELECT
    d.fiscal_year_label,
    d.fiscal_month_number,
    d.year_month AS calendar_month,
    COUNT(DISTINCT f.invoice_id) AS invoices,
    SUM(f.quantity) AS quantity_sold,
    SUM(f.total_excluding_tax) AS sales_excluding_tax,
    SUM(f.total_including_tax) AS sales_including_tax,
    SUM(f.profit) AS profit
FROM asb_olap.fact_sale f
JOIN asb_olap.dim_date d ON d.date_key = f.invoice_date_key
GROUP BY d.fiscal_year_label, d.fiscal_month_number, d.year_month
ORDER BY d.fiscal_year_label, d.fiscal_month_number;
