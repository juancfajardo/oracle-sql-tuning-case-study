-- The SQL text is the same before and after the fix.
-- Before: the application binds :customer_code as a NUMBER  -> implicit TO_NUMBER() on the column.
-- After:  the application binds :customer_code as a STRING  -> unique index on customer_code is used.
SELECT /*+ gather_plan_statistics */ /* tag:case2 */
       o.order_id,
       o.order_date,
       o.status,
       o.total_amount
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
WHERE c.customer_code = :customer_code
ORDER BY o.order_date DESC, o.order_id DESC
FETCH FIRST 20 ROWS ONLY
/
