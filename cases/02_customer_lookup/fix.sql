-- Index on the foreign key, ordered by date, so "last 20 orders" stops after 20 index entries.
CREATE INDEX idx_orders_cust_date ON orders (customer_id, order_date, order_id)
/
BEGIN
  DBMS_STATS.GATHER_INDEX_STATS(USER, 'IDX_ORDERS_CUST_DATE');
END;
/
