-- Schema for the Oracle SQL tuning case study.
-- Requires Oracle Database 23ai (uses DROP ... IF EXISTS). Oracle Database Free works.
-- Every statement ends with a "/" line, so the file runs in SQL*Plus, SQLcl and bench/bench.py.

DROP TABLE IF EXISTS stg_price_upload PURGE
/
DROP TABLE IF EXISTS price_list PURGE
/
DROP TABLE IF EXISTS orders PURGE
/
DROP TABLE IF EXISTS customers PURGE
/

-- Customer codes are digits stored as text, as in many legacy systems.
CREATE TABLE customers (
  customer_id   NUMBER(10)    NOT NULL,
  customer_code VARCHAR2(20)  NOT NULL,
  name          VARCHAR2(100) NOT NULL,
  region_code   VARCHAR2(10)  NOT NULL,
  created_at    DATE          NOT NULL,
  CONSTRAINT pk_customers PRIMARY KEY (customer_id),
  CONSTRAINT uq_customers_code UNIQUE (customer_code)
)
/

CREATE TABLE orders (
  order_id     NUMBER(12)   NOT NULL,
  customer_id  NUMBER(10)   NOT NULL,
  order_date   DATE         NOT NULL,
  status       VARCHAR2(12) NOT NULL,
  total_amount NUMBER(14,2) NOT NULL,
  CONSTRAINT pk_orders PRIMARY KEY (order_id),
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
)
/

-- The "existing" index a team usually already has.
CREATE INDEX idx_orders_date ON orders (order_date)
/

-- Price list loaded from files. Starts without a key, as in the original system.
CREATE TABLE price_list (
  sku        VARCHAR2(30) NOT NULL,
  valid_from DATE         NOT NULL,
  price      NUMBER(12,2) NOT NULL,
  updated_at DATE         NOT NULL
)
/

-- Staging table that receives each uploaded file.
CREATE TABLE stg_price_upload (
  sku        VARCHAR2(30) NOT NULL,
  valid_from DATE         NOT NULL,
  price      NUMBER(12,2) NOT NULL,
  loaded_at  TIMESTAMP    NOT NULL
)
/
