-- Q5a: Salespeople ranked by invoiced sales, with the value of the orders they managed.
WITH s AS (
    SELECT salesperson_key, COUNT(DISTINCT invoice_id) AS invoices,
           SUM(total_including_tax) AS sales_including_tax, SUM(profit) AS profit
    FROM asb_olap.fact_sale GROUP BY salesperson_key
),
o AS (
    SELECT salesperson_key, COUNT(DISTINCT order_id) AS orders,
           SUM(total_including_tax) AS ordered_value_including_tax
    FROM asb_olap.fact_order GROUP BY salesperson_key
)
SELECT
    e.full_name AS salesperson,
    o.orders,
    o.ordered_value_including_tax,
    s.invoices,
    s.sales_including_tax,
    s.profit,
    RANK() OVER (ORDER BY s.sales_including_tax DESC) AS sales_rank
FROM asb_olap.dim_employee e
LEFT JOIN o ON o.salesperson_key = e.employee_key
LEFT JOIN s ON s.salesperson_key = e.employee_key
WHERE o.orders IS NOT NULL OR s.invoices IS NOT NULL
ORDER BY sales_rank;
