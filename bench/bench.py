"""Benchmark harness for the Oracle SQL tuning case study.

Runs every case "before" and "after" on the same data, checks that both versions
return the same result, and writes the measurements to results/.

Usage:
    pip install -r bench/requirements.txt
    python bench/bench.py --setup --system-password <pwd>   # first run: grants, schema, data
    python bench/bench.py                                    # run the benchmark again
    python bench/bench.py --quick                            # smaller data, for a fast smoke test

Uses python-oracledb in thin mode: no Oracle Client installation is needed.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import statistics
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import oracledb

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "cases"
RESULTS = ROOT / "results"

FULL = {"n_customers": 100_000, "n_orders": 2_000_000, "n_skus": 50_000, "n_stg": 20_000, "lookups": 50}
QUICK = {"n_customers": 20_000, "n_orders": 200_000, "n_skus": 10_000, "n_stg": 4_000, "lookups": 20}


# --------------------------------------------------------------------------- SQL file helpers

def split_statements(text: str) -> list[str]:
    """Split a .sql file on lines that contain only '/' (SQL*Plus convention)."""
    chunks, current = [], []
    for line in text.splitlines():
        if line.strip() == "/":
            chunk = "\n".join(current).strip()
            if chunk:
                chunks.append(chunk)
            current = []
        else:
            current.append(line)
    tail = "\n".join(current).strip()
    if strip_comments(tail).strip():
        chunks.append(tail)
    return [c for c in chunks if strip_comments(c).strip()]


def strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def bind_names(sql: str) -> set[str]:
    code = strip_comments(sql)
    code = re.sub(r"'(?:[^']|'')*'", "''", code)  # ignore string literals
    return {m.lower() for m in re.findall(r":([A-Za-z_]\w*)", code)}


def clean_for_exec(sql: str) -> str:
    """Drop full-line comments; keep inline comments and hints."""
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    sql = "\n".join(lines).strip()
    # A plain SQL statement must not end with ';' when sent through the driver. PL/SQL blocks must.
    if not re.match(r"(?is)^\s*(begin|declare)\b", sql) and sql.endswith(";"):
        sql = sql[:-1]
    return sql


def run_file(conn, path: Path, binds: dict | None = None) -> None:
    binds = binds or {}
    with conn.cursor() as cur:
        for stmt in split_statements(path.read_text(encoding="utf-8")):
            names = bind_names(stmt)
            cur.execute(clean_for_exec(stmt), {k: v for k, v in binds.items() if k in names})
    conn.commit()


def load_query(path: Path) -> str:
    stmts = split_statements(path.read_text(encoding="utf-8"))
    assert len(stmts) == 1, f"{path} must contain exactly one statement"
    return clean_for_exec(stmts[0])


# --------------------------------------------------------------------------- measurement helpers

class Stats:
    """Reads session statistics. Needs SELECT_CATALOG_ROLE; degrades gracefully without it."""

    def __init__(self, conn):
        self.conn = conn
        self.available = True
        try:
            self.logical_reads()
        except oracledb.DatabaseError:
            self.available = False
            print("  ! No access to V$ views: logical reads and plans will be skipped.\n"
                  "    Run once with --setup --system-password <pwd> to grant SELECT_CATALOG_ROLE.")

    def logical_reads(self) -> int | None:
        if not getattr(self, "available", True):
            return None
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT ms.value
                FROM v$mystat ms
                JOIN v$statname sn ON sn.statistic# = ms.statistic#
                WHERE sn.name = 'session logical reads'""")
            return int(cur.fetchone()[0])

    def plan(self, tag: str) -> str | None:
        if not self.available:
            return None
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT sql_id, child_number
                FROM v$sql
                WHERE sql_text LIKE :pattern
                  AND sql_text NOT LIKE '%v$sql%'
                ORDER BY last_active_time DESC
                FETCH FIRST 1 ROW ONLY""", pattern=f"%tag:{tag} %")
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("SELECT plan_table_output FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(:sql_id, :child, 'ALLSTATS LAST'))",
                        sql_id=row[0], child=row[1])
            return "\n".join(r[0] for r in cur.fetchall())


def timed_query(conn, sql: str, binds: dict) -> tuple[list, float]:
    with conn.cursor() as cur:
        cur.arraysize = 500
        start = time.perf_counter()
        cur.execute(sql, binds)
        rows = cur.fetchall()
        return rows, (time.perf_counter() - start) * 1000


def measure(conn, stats: Stats, fn, reps: int) -> dict:
    """Run fn once to warm up, then `reps` times. Returns median elapsed and logical reads per run."""
    result = fn()  # warm-up (buffer cache, parsed cursor); not measured
    times, reads = [], []
    for _ in range(reps):
        lr0 = stats.logical_reads()
        t0 = time.perf_counter()
        result = fn()
        times.append((time.perf_counter() - t0) * 1000)
        lr1 = stats.logical_reads()
        if lr0 is not None:
            reads.append(lr1 - lr0)
    return {
        "elapsed_ms": round(statistics.median(times), 2),
        "elapsed_ms_all": [round(t, 2) for t in times],
        "logical_reads": int(statistics.median(reads)) if reads else None,
        "result": result,
    }


def save_plan(stats: Stats, tag: str, name: str) -> None:
    text = stats.plan(tag)
    if text:
        (RESULTS / "plans" / f"{name}.txt").write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------- cases

def case1(conn, stats: Stats, cfg: dict, reps: int) -> dict:
    print("Case 1: monthly sales report")
    folder = CASES / "01_monthly_report"
    binds = {"month": cfg["month"]}
    run_file(conn, folder / "reset.sql")

    before_sql = load_query(folder / "before.sql")
    before = measure(conn, stats, lambda: timed_query(conn, before_sql, binds)[0], reps)
    save_plan(stats, "case1_before", "case1_before")
    print(f"  before: {before['elapsed_ms']} ms, {before['logical_reads']} logical reads")

    run_file(conn, folder / "fix.sql")
    after_sql = load_query(folder / "after.sql")
    after = measure(conn, stats, lambda: timed_query(conn, after_sql, binds)[0], reps)
    save_plan(stats, "case1_after", "case1_after")
    print(f"  after:  {after['elapsed_ms']} ms, {after['logical_reads']} logical reads")

    same = before.pop("result") == after.pop("result")
    print(f"  identical results: {same}")
    return {"title": "Monthly sales report", "unit": "per report",
            "before": before, "after": after, "identical_results": same}


def case2(conn, stats: Stats, cfg: dict, reps: int) -> dict:
    print("Case 2: customer order history lookup")
    folder = CASES / "02_customer_lookup"
    sql = load_query(folder / "query.sql")
    n, k = cfg["n_customers"], cfg["lookups"]
    codes = [str((i * (n // k)) + 1).zfill(8) for i in range(k)]  # fixed, evenly spread sample

    def run_all(as_number: bool):
        out = []
        for code in codes:
            value = int(code) if as_number else code
            out.append(timed_query(conn, sql, {"customer_code": value})[0])
        return out

    run_file(conn, folder / "reset.sql")
    before = measure(conn, stats, lambda: run_all(as_number=True), reps)
    save_plan(stats, "case2", "case2_before")
    print(f"  before: {before['elapsed_ms'] / k:.2f} ms per lookup")

    run_file(conn, folder / "fix.sql")
    after = measure(conn, stats, lambda: run_all(as_number=False), reps)
    save_plan(stats, "case2", "case2_after")
    print(f"  after:  {after['elapsed_ms'] / k:.2f} ms per lookup")

    same = before.pop("result") == after.pop("result")
    print(f"  identical results: {same}")
    for side in (before, after):  # report per lookup
        side["elapsed_ms"] = round(side["elapsed_ms"] / k, 3)
        side["elapsed_ms_all"] = [round(t / k, 3) for t in side["elapsed_ms_all"]]
        if side["logical_reads"] is not None:
            side["logical_reads"] = round(side["logical_reads"] / k)
    return {"title": "Customer order lookup (API call)", "unit": "per lookup", "lookups": k,
            "before": before, "after": after, "identical_results": same}


def price_list_state(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*),
                   SUM(price),
                   (SELECT COUNT(*) FROM (SELECT sku, valid_from FROM price_list
                                          GROUP BY sku, valid_from HAVING COUNT(*) > 1))
            FROM price_list""")
        rows, total, dup_keys = cur.fetchone()
        return {"rows": int(rows), "price_sum": float(total), "duplicate_keys": int(dup_keys)}


def run_block(conn, stats: Stats, path: Path) -> dict:
    block = clean_for_exec(split_statements(path.read_text(encoding="utf-8"))[0])
    lr0 = stats.logical_reads()
    t0 = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute(block)
    elapsed = (time.perf_counter() - t0) * 1000
    lr1 = stats.logical_reads()
    return {"elapsed_ms": round(elapsed, 2), "logical_reads": (lr1 - lr0) if lr0 is not None else None}


def double_submission(connect, path: Path) -> float:
    """Two sessions load the same file at the same time (a retry or a double click)."""
    block = clean_for_exec(split_statements(path.read_text(encoding="utf-8"))[0])
    errors: list[str] = []
    barrier = threading.Barrier(2)

    def worker():
        try:
            with connect() as c, c.cursor() as cur:
                barrier.wait()
                cur.execute(block)
        except Exception as exc:  # report, do not hide
            errors.append(str(exc))

    t0 = time.perf_counter()
    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        print("  ! errors during double submission:", *errors, sep="\n    ")
    return round((time.perf_counter() - t0) * 1000, 2)


def case3(conn, connect, stats: Stats, cfg: dict) -> dict:
    print("Case 3: bulk price upload")
    folder = CASES / "03_bulk_price_upload"
    binds = {"n_skus": cfg["n_skus"], "n_stg": cfg["n_stg"]}

    run_file(conn, folder / "reset.sql", binds)
    before = run_block(conn, stats, folder / "before.sql")
    before_state = price_list_state(conn)
    print(f"  before: {before['elapsed_ms'] / 1000:.1f} s for {cfg['n_stg']} lines")

    run_file(conn, folder / "reset.sql", binds)
    run_file(conn, folder / "fix.sql")
    after = run_block(conn, stats, folder / "after.sql")
    after_state = price_list_state(conn)
    print(f"  after:  {after['elapsed_ms'] / 1000:.2f} s")

    same = (before_state["rows"] == after_state["rows"]
            and abs(before_state["price_sum"] - after_state["price_sum"]) < 0.005)
    print(f"  identical final price list: {same}")

    print("  double submission test (2 sessions, same file, same time)...")
    run_file(conn, folder / "reset.sql", binds)
    before_dbl_ms = double_submission(connect, folder / "before.sql")
    before_dbl = price_list_state(conn)
    run_file(conn, folder / "reset.sql", binds)
    run_file(conn, folder / "fix.sql")
    after_dbl_ms = double_submission(connect, folder / "after.sql")
    after_dbl = price_list_state(conn)
    print(f"  duplicate keys: before={before_dbl['duplicate_keys']}, after={after_dbl['duplicate_keys']}")

    return {"title": "Bulk price upload", "unit": "per file", "file_lines": cfg["n_stg"],
            "before": {**before, **before_state}, "after": {**after, **after_state},
            "identical_results": same,
            "double_submission": {
                "before": {"elapsed_ms": before_dbl_ms, **before_dbl},
                "after": {"elapsed_ms": after_dbl_ms, **after_dbl},
            }}


# --------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsn", default="localhost:1521/FREEPDB1")
    ap.add_argument("--user", default="demo")
    ap.add_argument("--password", default="demo")
    ap.add_argument("--system-password", help="SYSTEM password, only needed with --setup to grant SELECT_CATALOG_ROLE")
    ap.add_argument("--setup", action="store_true", help="create schema and load data before benchmarking")
    ap.add_argument("--quick", action="store_true", help="small data set for a fast smoke test")
    ap.add_argument("--month", default="2025-06", help="month used by case 1 (YYYY-MM, between 2023-01 and 2025-12)")
    ap.add_argument("--reps", type=int, default=5, help="measured repetitions per query (after one warm-up)")
    ap.add_argument("--only", choices=["1", "2", "3"], action="append", help="run only some cases")
    args = ap.parse_args()

    cfg = dict(QUICK if args.quick else FULL, month=args.month)
    (RESULTS / "plans").mkdir(parents=True, exist_ok=True)

    def connect():
        return oracledb.connect(user=args.user, password=args.password, dsn=args.dsn)

    if args.setup and args.system_password:
        with oracledb.connect(user="system", password=args.system_password, dsn=args.dsn) as sysconn:
            with sysconn.cursor() as cur:
                cur.execute(f"GRANT SELECT_CATALOG_ROLE TO {args.user}")
        print("Granted SELECT_CATALOG_ROLE")

    with connect() as conn:
        if args.setup:
            print("Creating schema and loading data (a few minutes)...")
            t0 = time.perf_counter()
            run_file(conn, ROOT / "sql" / "01_schema.sql")
            run_file(conn, ROOT / "sql" / "02_seed_data.sql", cfg)
            with conn.cursor() as cur:
                cur.execute("BEGIN DBMS_STATS.GATHER_SCHEMA_STATS(USER); END;")
            print(f"  done in {time.perf_counter() - t0:.0f} s")

        stats = Stats(conn)
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT banner_full FROM v$version")
                db_version = cur.fetchone()[0]
            except oracledb.DatabaseError:
                db_version = conn.version

        selected = set(args.only or ["1", "2", "3"])
        results = {}
        if "1" in selected:
            results["case1"] = case1(conn, stats, cfg, args.reps)
        if "2" in selected:
            results["case2"] = case2(conn, stats, cfg, max(1, args.reps // 2))
        if "3" in selected:
            results["case3"] = case3(conn, connect, stats, cfg)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "database": db_version,
        "client": f"python-oracledb {oracledb.__version__} (thin), Python {platform.python_version()}",
        "machine": platform.platform(),
        "data": {k: cfg[k] for k in ("n_customers", "n_orders", "n_skus", "n_stg")},
        "method": "median of repeated runs after one warm-up run (warm buffer cache); "
                  "logical reads from V$MYSTAT 'session logical reads'",
        "cases": results,
    }
    out = RESULTS / "summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {out.relative_to(ROOT)}. Next: python bench/charts.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
