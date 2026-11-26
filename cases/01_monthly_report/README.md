# Case 1: Monthly sales report

**Symptom:** the monthly sales report by region gets slower every month, even though it only reads one month.

**Root cause:** the filter wraps the indexed column in a function:

```sql
WHERE TO_CHAR(o.order_date, 'YYYY-MM') = :month
```

Oracle has to compute `TO_CHAR` for every row of `orders`, so the index on `order_date` cannot be used and the whole table is read. The table grows every day, and so does the report time.

**Fix:**

1. Rewrite the filter as a date range on the bare column (`>= first day` and `< first day of next month`). The index becomes usable again.
2. Add a covering index `(order_date, status, customer_id, total_amount)`, so the report reads one month of index entries and never touches the table.

Files:

- `before.sql`: the original query
- `fix.sql`: the index
- `after.sql`: the rewritten query

Same result, same columns, same order: the benchmark checks that both versions return identical rows.
