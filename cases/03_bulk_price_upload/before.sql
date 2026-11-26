-- Original upload: one file line at a time, check-then-write, commit per row.
BEGIN
  FOR r IN (SELECT sku, valid_from, price
            FROM stg_price_upload
            ORDER BY loaded_at) LOOP
    DECLARE
      v_count NUMBER;
    BEGIN
      SELECT COUNT(*)
      INTO v_count
      FROM price_list
      WHERE sku = r.sku
        AND valid_from = r.valid_from;

      IF v_count = 0 THEN
        INSERT INTO price_list (sku, valid_from, price, updated_at)
        VALUES (r.sku, r.valid_from, r.price, SYSDATE);
      ELSE
        UPDATE price_list
        SET price = r.price,
            updated_at = SYSDATE
        WHERE sku = r.sku
          AND valid_from = r.valid_from;
      END IF;

      COMMIT;
    END;
  END LOOP;
END;
/
