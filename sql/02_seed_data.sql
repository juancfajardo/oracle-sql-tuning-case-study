-- Synthetic, reproducible data. No real customer data is used anywhere in this repo.
-- Bind variables (set by bench/bench.py):
--   :n_customers  number of customers   (default 100,000)
--   :n_orders     number of orders      (default 2,000,000, spread over 2023-2025)
--   :n_skus       number of products    (default 50,000; price_list gets 4 rows per SKU)
-- ORA_HASH with fixed seeds makes every run generate exactly the same data.

BEGIN
  INSERT /*+ APPEND */ INTO customers (customer_id, customer_code, name, region_code, created_at)
  SELECT level,
         LPAD(level, 8, '0'),
         'Customer ' || level,
         'R' || LPAD(MOD(level, 24) + 1, 2, '0'),
         DATE '2020-01-01' + MOD(level, 1500)
  FROM dual
  CONNECT BY level <= :n_customers;
  COMMIT;

  INSERT /*+ APPEND */ INTO orders (order_id, customer_id, order_date, status, total_amount)
  SELECT g.rn,
         MOD(ORA_HASH(g.rn, 4294967295, 1), :n_customers) + 1,
         DATE '2023-01-01' + MOD(ORA_HASH(g.rn, 4294967295, 2), 1095) + MOD(g.rn, 86400) / 86400,
         CASE MOD(ORA_HASH(g.rn, 4294967295, 3), 20)
           WHEN 0 THEN 'CANCELLED'
           WHEN 1 THEN 'PENDING'
           ELSE 'INVOICED'
         END,
         ROUND(10 + MOD(ORA_HASH(g.rn, 4294967295, 4), 500000) / 100, 2)
  FROM (
    SELECT (a.n - 1) * 1000 + b.n AS rn
    FROM (SELECT level AS n FROM dual CONNECT BY level <= CEIL(:n_orders / 1000)) a
    CROSS JOIN (SELECT level AS n FROM dual CONNECT BY level <= 1000) b
  ) g
  WHERE g.rn <= :n_orders;
  COMMIT;
END;
/
