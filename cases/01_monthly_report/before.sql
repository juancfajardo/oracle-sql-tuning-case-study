SELECT /*+ gather_plan_statistics */ /* tag:case1_before */
       c.region_code,
       COUNT(*)            AS orders_count,
       SUM(o.total_amount) AS total_sales
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE TO_CHAR(o.order_date, 'YYYY-MM') = :month
  AND o.status <> 'CANCELLED'
GROUP BY c.region_code
ORDER BY c.region_code
/
