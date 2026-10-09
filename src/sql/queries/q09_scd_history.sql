-- Q9: How have the tracked customer attributes (category, buying group, delivery city) changed over time?
SELECT customer_id, customer_name, version_number, customer_category_name, buying_group_name,
       delivery_city_name, effective_start_date, effective_end_date, is_current
FROM (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY effective_start_date) AS version_number,
           COUNT(*) OVER (PARTITION BY customer_id) AS versions
    FROM asb_olap.dim_customer
    WHERE customer_id IS NOT NULL
)
WHERE versions > 1
ORDER BY customer_id, version_number;
