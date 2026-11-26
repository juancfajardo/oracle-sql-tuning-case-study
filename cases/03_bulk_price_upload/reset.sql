-- Rebuilds the starting point for case 3, so "before" and "after" run on identical data.
-- Bind variables (set by bench/bench.py):
--   :n_skus  number of products; price_list starts with 4 prices per product
--   :n_stg   number of lines in the uploaded file
-- Half of the file updates existing prices (valid_from 2026-01-01), half adds new ones (2026-12-01).
-- Product codes are hashed, so the file naturally contains some repeated product/date pairs.

BEGIN
  BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE price_list DROP CONSTRAINT pk_price_list DROP INDEX';
  EXCEPTION
    WHEN OTHERS THEN
      IF SQLCODE != -2443 THEN  -- ORA-02443: constraint does not exist
        RAISE;
      END IF;
  END;

  EXECUTE IMMEDIATE 'TRUNCATE TABLE price_list';
  EXECUTE IMMEDIATE 'TRUNCATE TABLE stg_price_upload';

  INSERT /*+ APPEND */ INTO price_list (sku, valid_from, price, updated_at)
  SELECT 'SKU' || LPAD(s.n, 6, '0'),
         d.valid_from,
         ROUND(1 + MOD(ORA_HASH(s.n * 10 + d.k, 4294967295, 5), 100000) / 100, 2),
         DATE '2025-12-31'
  FROM (SELECT level AS n FROM dual CONNECT BY level <= :n_skus) s
  CROSS JOIN (
    SELECT 1 AS k, DATE '2025-01-01' AS valid_from FROM dual UNION ALL
    SELECT 2,      DATE '2025-07-01'               FROM dual UNION ALL
    SELECT 3,      DATE '2026-01-01'               FROM dual UNION ALL
    SELECT 4,      DATE '2026-07-01'               FROM dual
  ) d;
  COMMIT;

  INSERT INTO stg_price_upload (sku, valid_from, price, loaded_at)
  SELECT 'SKU' || LPAD(MOD(ORA_HASH(level, 4294967295, 7), :n_skus) + 1, 6, '0'),
         CASE WHEN MOD(level, 2) = 0 THEN DATE '2026-01-01' ELSE DATE '2026-12-01' END,
         ROUND(1 + MOD(ORA_HASH(level, 4294967295, 8), 100000) / 100, 2),
         TIMESTAMP '2026-11-01 08:00:00' + NUMTODSINTERVAL(level, 'SECOND')
  FROM dual
  CONNECT BY level <= :n_stg;
  COMMIT;

  DBMS_STATS.GATHER_TABLE_STATS(USER, 'PRICE_LIST');
  DBMS_STATS.GATHER_TABLE_STATS(USER, 'STG_PRICE_UPLOAD');
END;
/
