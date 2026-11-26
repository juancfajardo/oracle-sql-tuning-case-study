SELECT /*+ gather_plan_statistics */ /* tag:case1_after */
       c.region_code,
       COUNT(*)            AS orders_count,
       SUM(o.total_amount) AS total_sales
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_date >= TO_DATE(:month || '-01', 'YYYY-MM-DD')
  AND o.order_date <  ADD_MONTHS(TO_DATE(:month || '-01', 'YYYY-MM-DD'), 1)
  AND o.status <> 'CANCELLED'
GROUP BY c.region_code
ORDER BY c.region_code
/
