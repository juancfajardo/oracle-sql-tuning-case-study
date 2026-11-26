# Case 3: Bulk price upload

**Symptom:** uploading a 20,000-line price file takes well over a minute. When a user retries an upload that "seems stuck", the price list can end up with **duplicate prices** for the same product and date.

**Root cause:**

1. **Row-by-row processing.** For every line of the file, a PL/SQL loop runs `SELECT COUNT(*)` to check whether the price exists, then `INSERT` or `UPDATE`, then `COMMIT`. That is thousands of round trips through the SQL engine, and a commit per row.
2. **No index on the lookup key.** Each `COUNT(*)` scans the whole `price_list` table. The cost grows with *file size x table size*.
3. **No unique key.** "Check, then insert" is not atomic. Two sessions processing the same file at the same time (a retry, a double click, two app servers) both see "not found" and both insert. Nothing in the database stops it.

**Fix:**

1. One set-based `MERGE` from the staging table: Oracle does the whole file in a single statement.
2. A primary key on `(sku, valid_from)`: the database itself guarantees there are no duplicates, and the key's index makes the `MERGE` join fast.
3. The file may contain the same product and date twice. The `MERGE` source keeps only the last line per key (`ROW_NUMBER() ... ORDER BY loaded_at DESC`), which is exactly what the old loop ended up with, so the final data is identical.
4. `LOCK TABLE ... IN SHARE ROW EXCLUSIVE MODE` makes concurrent uploads wait for each other instead of colliding. Reads are never blocked.

Files:

- `before.sql`: the original row-by-row procedure
- `fix.sql`: the primary key
- `after.sql`: the set-based version
- `reset.sql`: rebuilds `price_list` and the staging file, so both versions start from the same data

The benchmark checks that both versions produce exactly the same final price list, and runs a "double submission" test (two sessions loading the same file at the same time) against each version.
