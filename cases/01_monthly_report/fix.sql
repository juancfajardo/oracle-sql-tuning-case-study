-- Covering index: the report is answered from the index alone.
CREATE INDEX idx_orders_date_cover ON orders (order_date, status, customer_id, total_amount)
/
BEGIN
  DBMS_STATS.GATHER_INDEX_STATS(USER, 'IDX_ORDERS_DATE_COVER');
END;
/
