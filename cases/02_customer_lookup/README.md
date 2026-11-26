# Case 2: Customer order history lookup

**Symptom:** an API endpoint that returns the last 20 orders of a customer is slow on every call, and gets slower as the orders table grows. The measured numbers are in the main README.

**Root cause (two problems at once):**

1. **Implicit conversion.** `customer_code` is a `VARCHAR2` column (codes like `00012345`), but the application binds the code as a **number**. To compare them, Oracle applies `TO_NUMBER(customer_code)` to every row, so the unique index on `customer_code` is ignored and `customers` is fully scanned on every call. The SQL text looks perfectly fine; the problem is only visible in the execution plan (`filter(TO_NUMBER("C"."CUSTOMER_CODE")=:CUSTOMER_CODE)`).
2. **Missing index on the foreign key.** `orders.customer_id` has no index, so finding one customer's orders means reading the whole `orders` table, and then sorting it.

**Fix:**

1. Bind `customer_code` as a string in the application (no SQL change).
2. Add an index on `orders (customer_id, order_date)`. Oracle reads the index backwards and stops after 20 rows (`FETCH FIRST`), with no sort.

Files:

- `query.sql`: the query (identical before and after)
- `fix.sql`: the index
- `reset.sql`: removes the index

The benchmark runs the same list of customer codes in both versions and checks that the results are identical.
