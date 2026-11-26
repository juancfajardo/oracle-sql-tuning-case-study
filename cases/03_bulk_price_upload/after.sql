-- Set-based upload: the whole file in one MERGE, one commit.
BEGIN
  -- Concurrent uploads queue up instead of colliding. Readers are never blocked.
  LOCK TABLE price_list IN SHARE ROW EXCLUSIVE MODE;

  MERGE INTO price_list t
  USING (
    -- If the file repeats a product/date, keep the last line (same result as the old loop).
    SELECT sku, valid_from, price
    FROM (
      SELECT sku,
             valid_from,
             price,
             ROW_NUMBER() OVER (PARTITION BY sku, valid_from ORDER BY loaded_at DESC) AS rn
      FROM stg_price_upload
    )
    WHERE rn = 1
  ) s
  ON (t.sku = s.sku AND t.valid_from = s.valid_from)
  WHEN MATCHED THEN
    UPDATE SET t.price = s.price,
               t.updated_at = SYSDATE
  WHEN NOT MATCHED THEN
    INSERT (sku, valid_from, price, updated_at)
    VALUES (s.sku, s.valid_from, s.price, SYSDATE);

  COMMIT;
END;
/
