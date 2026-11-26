# Oracle SQL Tuning Case Study

Three common performance problems in production Oracle systems, each one reproduced, fixed and **measured before and after on the same data**, with proof that the result did not change.

> **Status:** code, cases and benchmark harness are complete. The measured results (chart, table and execution plans) will be published here after the benchmark run on Oracle Database 23ai Free. No numbers are shown until they are measured.

| # | Problem | Root cause | Fix |
|---|---|---|---|
| 1 | [Monthly report gets slower every month](cases/01_monthly_report) | Function on an indexed column (`TO_CHAR(order_date)`) forces a full table scan | Date-range predicate + covering index |
| 2 | [API lookup is slow on every call](cases/02_customer_lookup) | Code bound as a number against a `VARCHAR2` column (implicit `TO_NUMBER`) + unindexed foreign key | Bind as string + `(customer_id, order_date)` index with `FETCH FIRST` stopkey |
| 3 | [Bulk upload takes minutes and can create duplicates on retry](cases/03_bulk_price_upload) | Row-by-row PL/SQL, commit per row, no key | One set-based `MERGE` + primary key + serialized loads |

## Results

*Pending benchmark run.* When it is done, the full numbers, execution plans and environment will be in `results/RESULTS.md` and `results/plans/`. Every chart and number is generated from `results/summary.json` by the scripts in `bench/`; nothing is typed by hand.

How to read them:

- **Elapsed time** is the median of several runs after a warm-up run, so the buffer cache is warm in both versions. Absolute times depend on the machine.
- **Logical reads** (blocks read from memory) do not depend on the machine. They are the most honest measure of how much work the database does.
- **Same result** means the benchmark compared the output of both versions row by row (cases 1 and 2) or compared the final table (case 3).

## How I approach a slow query

1. **Measure first.** Capture the real execution plan with row counts (`DBMS_XPLAN.DISPLAY_CURSOR` with `ALLSTATS LAST`) and the logical reads. No guessing.
2. **Find where the rows are lost.** Compare estimated and actual rows per plan step. The step that reads millions of rows to return a few hundred is the problem.
3. **Fix the cause, not the symptom.** Rewrite the predicate, fix the bind type, add the one index that serves the access path, or replace row-by-row code with a set-based statement. Hints are the last resort.
4. **Prove it.** Same data, same result, numbers before and after.

## Run it yourself

Requirements: Docker (or Podman) and Python 3.10+.

One command: `bash scripts/run.sh` (Linux/macOS) or `powershell -ExecutionPolicy Bypass -File scripts\run.ps1` (Windows). Or step by step:

```bash
docker compose up -d                       # Oracle Database 23ai Free; wait until it is healthy
pip install -r bench/requirements.txt
python bench/bench.py --setup --system-password ChangeMe_123   # creates schema + loads data, then benchmarks
python bench/charts.py                     # regenerates the chart, the table and the cover image
```

Options: `--quick` uses a small data set for a fast smoke test, `--only 1` runs a single case, `--dsn host:port/service` points to another Oracle Database 23ai instance (the scripts use 23ai syntax such as `DROP ... IF EXISTS`).

## Repository layout

```
sql/          schema and synthetic data generator (reproducible, no real data)
cases/        one folder per case: README, before, fix, after, reset
bench/        benchmark harness (python-oracledb, thin mode) and chart generator
scripts/      one-shot run scripts for Windows and Linux/macOS
results/      summary.json, RESULTS.md, execution plans, chart
docs/         cover image
```

## About me

I'm Juan Fajardo, a backend tech lead and architect for Java platforms (Spring Boot, Quarkus) with Oracle and SingleStore in production, ERP and legacy integration (SOAP, IBM MQ, AS400). I help teams make slow systems fast, with measurements before and after.

All data in this repository is synthetic. No code or data from any employer or client is included.

## License

MIT
