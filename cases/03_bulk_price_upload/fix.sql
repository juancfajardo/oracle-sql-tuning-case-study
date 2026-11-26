-- The database guarantees one price per product and date. The key's index also serves the MERGE join.
ALTER TABLE price_list ADD CONSTRAINT pk_price_list PRIMARY KEY (sku, valid_from)
/
