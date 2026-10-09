-- Q6: What proportion of ordered quantity is later invoiced? By fiscal year of the order, plus a total row.
SELECT
    COALESCE(d.fiscal_year_label, 'All years') AS fiscal_year,
    SUM(f.ordered_quantity) AS ordered_quantity,
    SUM(f.invoiced_quantity) AS invoiced_quantity,
    ROUND(100.0 * SUM(f.invoiced_quantity) / SUM(f.ordered_quantity), 2) AS pct_invoiced
FROM asb_olap.fact_order f
JOIN asb_olap.dim_date d ON d.date_key = f.order_date_key
GROUP BY ROLLUP (d.fiscal_year_label)
ORDER BY d.fiscal_year_label NULLS LAST;
