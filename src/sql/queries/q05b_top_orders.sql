-- Q5b: The 20 highest-value orders and the salesperson who managed each.
SELECT
    f.order_id,
    d.full_date AS order_date,
    e.full_name AS salesperson,
    c.customer_name,
    SUM(f.ordered_quantity) AS ordered_quantity,
    SUM(f.total_including_tax) AS order_value_including_tax
FROM asb_olap.fact_order f
JOIN asb_olap.dim_employee e ON e.employee_key = f.salesperson_key
JOIN asb_olap.dim_customer c ON c.customer_key = f.customer_key
JOIN asb_olap.dim_date d ON d.date_key = f.order_date_key
GROUP BY f.order_id, d.full_date, e.full_name, c.customer_name
ORDER BY order_value_including_tax DESC
LIMIT 20;
