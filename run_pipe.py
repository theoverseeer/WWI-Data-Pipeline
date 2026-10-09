"""
WWI data pipeline: raw CSV -> OLTP (DuckDB) -> OLAP (DuckDB, star schema).

ONE entry point:

    python run_pipe.py                      # load 1: full build (initial load)
    python src/03_make_batch2.py            # once: creates the second input batch
    python run_pipe.py --load 2             # load 2: SCD Type 2 changes flow through the pipeline
    python run_pipe.py --load 2             # run again: nothing changes (idempotent)

Steps (same order as the case study):
  1 validate source files         2 prepare OLTP database        3 ingest CSV into OLTP
  4 validate OLTP load            5 prepare OLAP + staging       6 load dimensions (incl. SCD2)
  7 load facts                    8 final data-quality checks    9 record pipeline result

Databases: asb_oltp.duckdb (OLTP), asb_olap.duckdb (OLAP + etl logging tables).
Critical data-quality failures stop the pipeline. Warnings are recorded and reported.
"""
import argparse
import logging
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
DATA_DIR = "data"
BATCH2_DIR = "data/batch2"
OLTP_DB = "asb_oltp.duckdb"
OLAP_DB = "asb_olap.duckdb"
OLTP_SQL = ROOT / "src" / "sql" / "oltp"
OLAP_SQL = ROOT / "src" / "sql" / "olap"
QUERY_SQL = ROOT / "src" / "sql" / "queries"
MACROS_SQL = ROOT / "src" / "sql" / "macros.sql"
DIMENSIONS = ["dim_date", "dim_city", "dim_employee", "dim_stock_item", "bridge_stock_item_group", "dim_customer"]
FACTS = ["fact_order", "fact_sale"]
COUNTED_TABLES = ["dim_date", "dim_city", "dim_employee", "dim_stock_item", "dim_customer", "fact_order", "fact_sale"]

ETL_DDL = """
CREATE SCHEMA IF NOT EXISTS asb_olap.etl;
CREATE TABLE IF NOT EXISTS asb_olap.etl.pipeline_run (run_id VARCHAR, load_no INTEGER, effective_date DATE,
    started_at TIMESTAMP, finished_at TIMESTAMP, status VARCHAR, message VARCHAR);
CREATE TABLE IF NOT EXISTS asb_olap.etl.step_log (run_id VARCHAR, step_no INTEGER, step_name VARCHAR,
    status VARCHAR, started_at TIMESTAMP, finished_at TIMESTAMP, message VARCHAR);
CREATE TABLE IF NOT EXISTS asb_olap.etl.ingestion_log (run_id VARCHAR, load_no INTEGER, table_name VARCHAR,
    source_file VARCHAR, rows_in_file BIGINT, rows_loaded BIGINT, ingested_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS asb_olap.etl.table_counts (run_id VARCHAR, load_no INTEGER, table_name VARCHAR, row_count BIGINT);
CREATE TABLE IF NOT EXISTS asb_olap.etl.dq_results (run_id VARCHAR, stage VARCHAR, check_name VARCHAR,
    table_name VARCHAR, severity VARCHAR, status VARCHAR, failed_rows BIGINT, checked_at TIMESTAMP);
"""


class PipelineError(Exception):
    pass


@dataclass
class Ctx:
    con: object
    run_id: str
    load: int
    effective_date: str
    skip_ingest: bool
    log: logging.Logger


# ----------------------------------------------------------------------------- helpers
def strip_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def run_sql_text(con, sql: str, subs: dict = None) -> None:
    sql = strip_comments(sql)
    for key, value in (subs or {}).items():
        sql = sql.replace(key, value)
    for stmt in (s.strip() for s in sql.split(";")):
        if stmt:
            con.execute(stmt)


def open_db():
    """One connection: OLTP is the main database, OLAP is attached as asb_olap."""
    con = duckdb.connect(str(ROOT / OLTP_DB))
    con.execute(f"ATTACH '{(ROOT / OLAP_DB).as_posix()}' AS asb_olap")
    run_sql_text(con, ETL_DDL)
    run_sql_text(con, MACROS_SQL.read_text(encoding="utf-8"))
    return con


def one(ctx, sql: str, params=None):
    return ctx.con.execute(sql, params or []).fetchone()[0]


def record_dq(ctx, stage, check, table, severity, failed) -> str:
    status = "INFO" if severity == "INFO" else ("PASS" if failed == 0 else ("FAIL" if severity == "CRITICAL" else "WARN"))
    ctx.con.execute("INSERT INTO asb_olap.etl.dq_results VALUES (?,?,?,?,?,?,?,?)",
                    [ctx.run_id, stage, check, table, severity, status, int(failed), datetime.now()])
    level = logging.ERROR if status == "FAIL" else (logging.WARNING if status == "WARN" else logging.INFO)
    ctx.log.log(level, "  [%-4s] %-48s %-28s rows=%s", status, check, table, failed)
    return status


def finish_dq(ctx, statuses, label) -> None:
    ctx.log.info("  %s: %d PASS, %d WARN, %d INFO, %d FAIL", label, statuses.count("PASS"),
                 statuses.count("WARN"), statuses.count("INFO"), statuses.count("FAIL"))
    if "FAIL" in statuses:
        raise PipelineError(f"{statuses.count('FAIL')} critical data-quality check(s) failed (see etl.dq_results)")


def oltp_tables():
    """[(sql_file, 'schema.table', csv_file_name)] for every OLTP script of the boilerplate."""
    out = []
    for f in sorted(OLTP_SQL.glob("*.sql")):
        m = re.search(r"CREATE OR REPLACE TABLE\s+([\w.]+)", f.read_text(encoding="utf-8"))
        out.append((f, m.group(1), f.stem + ".csv"))
    return out


def csv_location(ctx, csv_name: str) -> str:
    if ctx.load == 2 and (ROOT / BATCH2_DIR / csv_name).exists():
        return f"{BATCH2_DIR}/{csv_name}"
    return f"{DATA_DIR}/{csv_name}"


# ----------------------------------------------------------------------------- step 1
def validate_sources(ctx):
    problems = []
    for f, table, csv_name in oltp_tables():
        path = ROOT / DATA_DIR / csv_name
        if not path.exists() or path.stat().st_size == 0:
            problems.append(f"missing or empty: {DATA_DIR}/{csv_name}")
            continue
        text = f.read_text(encoding="utf-8")
        wanted = re.findall(r"^\s*,?\s*(\w+)\s*$", text.split("SELECT", 1)[1].split("FROM", 1)[0], re.M)
        with open(path, encoding="utf-8-sig") as fh:
            header = fh.readline().strip().split(";")
        missing = [c for c in wanted if c not in header]
        if missing:
            problems.append(f"{csv_name}: columns not found {missing}")
    if ctx.load == 2 and not (ROOT / BATCH2_DIR / "Sales.Customers.csv").exists():
        problems.append("load 2 needs data/batch2/Sales.Customers.csv: run  python src/03_make_batch2.py  first")
    if problems:
        raise PipelineError("source validation failed:\n    - " + "\n    - ".join(problems) +
                            "\n  (the CSV files must be directly inside the data/ folder)")
    ctx.log.info("  %d source files found and structurally valid", len(oltp_tables()))


# ----------------------------------------------------------------------------- step 2
def prepare_oltp(ctx):
    for schema in ("application", "purchasing", "sales", "warehouse"):
        ctx.con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    ctx.log.info("  databases ready: %s (OLTP), %s (OLAP + etl logging)", OLTP_DB, OLAP_DB)


# ----------------------------------------------------------------------------- step 3
def ingest(ctx):
    if ctx.load == 1 and not ctx.skip_ingest:
        ctx.con.close()                      # the ingestion script needs the OLTP file lock
        try:
            subprocess.run([sys.executable, "src/01_ingest_csv.py"], cwd=ROOT, check=True)
        finally:
            ctx.con = open_db()
    elif ctx.load == 2:
        # Batch 2 = a new extract of Sales.Customers. Same boilerplate script, different folder.
        sql = (OLTP_SQL / "Sales.Customers.sql").read_text(encoding="utf-8").format(folder_path=BATCH2_DIR)
        ctx.con.execute(sql)
        ctx.log.info("  loaded batch 2 customer extract from %s", BATCH2_DIR)
    else:
        ctx.log.info("  --skip-ingest: keeping the existing OLTP tables")

    for _, table, csv_name in oltp_tables():
        loc = csv_location(ctx, csv_name)
        in_file = one(ctx, f"SELECT COUNT(*) FROM read_csv('{loc}', header=true, delim=';', all_varchar=true)")
        in_table = one(ctx, f"SELECT COUNT(*) FROM {table}")
        ctx.con.execute("INSERT INTO asb_olap.etl.ingestion_log VALUES (?,?,?,?,?,?,?)",
                        [ctx.run_id, ctx.load, table, loc, in_file, in_table, datetime.now()])
        ctx.log.info("  %-34s file_rows=%9s  table_rows=%9s", table, f"{in_file:,}", f"{in_table:,}")


# ----------------------------------------------------------------------------- step 4
PK = {
    "sales.customers": "CustomerID", "sales.orders": "OrderID", "sales.order_lines": "OrderLineID",
    "sales.invoices": "InvoiceID", "sales.invoice_lines": "InvoiceLineID", "warehouse.stock_items": "StockItemID",
    "application.people": "PersonID", "application.cities": "CityID", "application.state_provinces": "StateProvinceID",
    "application.countries": "CountryID", "sales.customer_categories": "CustomerCategoryID",
    "sales.buying_groups": "BuyingGroupID", "warehouse.colors": "ColorID", "warehouse.package_types": "PackageTypeID",
    "purchasing.suppliers": "SupplierID", "application.delivery_methods": "DeliveryMethodID",
    "warehouse.stock_groups": "StockGroupID",
}
FK = [  # (child table, column, parent table)  parent key = PK[parent]
    ("sales.customers", "CustomerCategoryID", "sales.customer_categories"),
    ("sales.customers", "BuyingGroupID", "sales.buying_groups"),
    ("sales.customers", "DeliveryCityID", "application.cities"),
    ("sales.customers", "BillToCustomerID", "sales.customers"),
    ("sales.customers", "PrimaryContactPersonID", "application.people"),
    ("sales.orders", "CustomerID", "sales.customers"),
    ("sales.orders", "SalespersonPersonID", "application.people"),
    ("sales.order_lines", "OrderID", "sales.orders"),
    ("sales.order_lines", "StockItemID", "warehouse.stock_items"),
    ("sales.invoices", "OrderID", "sales.orders"),
    ("sales.invoices", "CustomerID", "sales.customers"),
    ("sales.invoices", "SalespersonPersonID", "application.people"),
    ("sales.invoice_lines", "InvoiceID", "sales.invoices"),
    ("sales.invoice_lines", "StockItemID", "warehouse.stock_items"),
    ("application.cities", "StateProvinceID", "application.state_provinces"),
    ("application.state_provinces", "CountryID", "application.countries"),
    ("warehouse.stock_items", "SupplierID", "purchasing.suppliers"),
    ("warehouse.stock_items", "ColorID", "warehouse.colors"),
]
OLTP_RULES = [  # warnings: business-rule violations that are reported, not fatal
    ("order_line_quantity_positive", "sales.order_lines", "SELECT COUNT(*) FROM sales.order_lines WHERE wwi_int(Quantity) IS NULL OR wwi_int(Quantity) <= 0"),
    ("invoice_line_quantity_positive", "sales.invoice_lines", "SELECT COUNT(*) FROM sales.invoice_lines WHERE wwi_int(Quantity) IS NULL OR wwi_int(Quantity) <= 0"),
    ("order_line_price_not_negative", "sales.order_lines", "SELECT COUNT(*) FROM sales.order_lines WHERE wwi_dec2(UnitPrice) IS NULL OR wwi_dec2(UnitPrice) < 0"),
    ("invoice_line_price_not_negative", "sales.invoice_lines", "SELECT COUNT(*) FROM sales.invoice_lines WHERE wwi_dec2(UnitPrice) IS NULL OR wwi_dec2(UnitPrice) < 0"),
    ("invoice_line_extended_price_formula", "sales.invoice_lines", "SELECT COUNT(*) FROM sales.invoice_lines WHERE ABS(wwi_dec2(ExtendedPrice) - (wwi_int(Quantity) * wwi_dec2(UnitPrice) + wwi_dec2(TaxAmount))) > 0.01"),
    ("order_date_valid", "sales.orders", "SELECT COUNT(*) FROM sales.orders WHERE wwi_date(OrderDate) IS NULL OR wwi_date(OrderDate) < DATE '2000-01-01' OR wwi_date(OrderDate) > CURRENT_DATE"),
    ("invoice_date_valid", "sales.invoices", "SELECT COUNT(*) FROM sales.invoices WHERE wwi_date(InvoiceDate) IS NULL OR wwi_date(InvoiceDate) < DATE '2000-01-01' OR wwi_date(InvoiceDate) > CURRENT_DATE"),
    ("expected_delivery_not_before_order", "sales.orders", "SELECT COUNT(*) FROM sales.orders WHERE wwi_date(ExpectedDeliveryDate) < wwi_date(OrderDate)"),
    ("invoice_not_before_order", "sales.invoices", "SELECT COUNT(*) FROM sales.invoices i JOIN sales.orders o ON wwi_int(i.OrderID) = wwi_int(o.OrderID) WHERE wwi_date(i.InvoiceDate) < wwi_date(o.OrderDate)"),
    ("delivery_not_before_invoice", "sales.invoices", "SELECT COUNT(*) FROM sales.invoices WHERE CAST(wwi_ts(ConfirmedDeliveryTime) AS DATE) < wwi_date(InvoiceDate)"),
]


def validate_oltp(ctx):
    results = []
    for rows_in, rows_loaded, table in ctx.con.execute(
            "SELECT rows_in_file, rows_loaded, table_name FROM asb_olap.etl.ingestion_log WHERE run_id = ?", [ctx.run_id]).fetchall():
        results.append(record_dq(ctx, "oltp", "table_rows_equal_file_rows", table, "CRITICAL", abs(rows_in - rows_loaded)))
    for table, pk in PK.items():
        results.append(record_dq(ctx, "oltp", "pk_not_null", table, "CRITICAL", one(ctx, f"SELECT COUNT(*) FROM {table} WHERE wwi_int({pk}) IS NULL")))
        results.append(record_dq(ctx, "oltp", "pk_unique", table, "CRITICAL", one(ctx, f"SELECT COUNT(*) FROM (SELECT wwi_int({pk}) FROM {table} GROUP BY 1 HAVING COUNT(*) > 1)")))
    for child, col, parent in FK:
        ppk = PK[parent]
        results.append(record_dq(ctx, "oltp", f"fk_{col}", child, "CRITICAL", one(
            ctx, f"SELECT COUNT(*) FROM {child} WHERE wwi_int({col}) IS NOT NULL AND wwi_int({col}) NOT IN (SELECT wwi_int({ppk}) FROM {parent})")))
    for check, table, sql in OLTP_RULES:
        results.append(record_dq(ctx, "oltp", check, table, "WARNING", one(ctx, sql)))
    finish_dq(ctx, results, "OLTP validation")


# ----------------------------------------------------------------------------- step 5
def prepare_olap(ctx):
    if ctx.load == 2:
        exists = one(ctx, "SELECT COUNT(*) FROM information_schema.tables WHERE table_catalog='asb_olap' AND table_name='dim_customer'")
        if not exists:
            raise PipelineError("load 2 is incremental: run  python run_pipe.py  (load 1) first")
    else:
        ctx.con.execute("DROP TABLE IF EXISTS asb_olap.dim_customer")   # load 1 = initial build, SCD history starts fresh
        ctx.log.info("  load 1: SCD dimension reset for the initial load")
    ctx.log.info("  staging tables (stg_customer, chg_customer) are created inside dim_customer.sql")


# ----------------------------------------------------------------------------- steps 6 and 7
def run_olap_file(ctx, name: str):
    text = (OLAP_SQL / f"{name}.sql").read_text(encoding="utf-8")
    if name == "dim_customer":    # incremental SCD script, already uses asb_olap.* names
        run_sql_text(ctx.con, text, {"@EFFECTIVE_DATE@": ctx.effective_date, "@RUN_ID@": ctx.run_id})
    else:                         # full rebuild: create the table in the OLAP database
        run_sql_text(ctx.con, text.replace("CREATE OR REPLACE TABLE ", "CREATE OR REPLACE TABLE asb_olap.", 1))
    rows = one(ctx, f"SELECT COUNT(*) FROM asb_olap.{name}")
    ctx.log.info("  %-26s rows=%s", name, f"{rows:,}")


def load_dimensions(ctx):
    for name in DIMENSIONS:
        run_olap_file(ctx, name)
    versions = one(ctx, "SELECT COUNT(*) FROM asb_olap.dim_customer WHERE customer_key > 0")
    current = one(ctx, "SELECT COUNT(*) FROM asb_olap.dim_customer WHERE customer_key > 0 AND is_current")
    ctx.log.info("  dim_customer: %d versions, %d current", versions, current)


def load_facts(ctx):
    for name in FACTS:
        run_olap_file(ctx, name)


# ----------------------------------------------------------------------------- step 8
def olap_checks():
    d = "asb_olap."
    c = []
    for dim, key in (("dim_date", "date_key"), ("dim_city", "city_key"), ("dim_employee", "employee_key"),
                     ("dim_stock_item", "stock_item_key"), ("dim_customer", "customer_key")):
        c.append((f"{key}_unique", dim, "CRITICAL", f"SELECT COUNT(*) FROM (SELECT {key} FROM {d}{dim} GROUP BY 1 HAVING COUNT(*) > 1)"))
    for dim, bk in (("dim_city", "city_id"), ("dim_employee", "person_id"), ("dim_stock_item", "stock_item_id")):
        c.append((f"{bk}_business_key_unique", dim, "CRITICAL", f"SELECT COUNT(*) FROM (SELECT {bk} FROM {d}{dim} WHERE {bk} IS NOT NULL GROUP BY 1 HAVING COUNT(*) > 1)"))
    c += [
        ("scd_exactly_one_current_row_per_customer", "dim_customer", "CRITICAL",
         f"SELECT COUNT(*) FROM (SELECT customer_id FROM {d}dim_customer WHERE customer_id IS NOT NULL GROUP BY 1 HAVING SUM(CASE WHEN is_current THEN 1 ELSE 0 END) <> 1)"),
        ("scd_no_overlapping_date_ranges", "dim_customer", "CRITICAL",
         f"SELECT COUNT(*) FROM {d}dim_customer a JOIN {d}dim_customer b ON a.customer_id = b.customer_id AND a.customer_key < b.customer_key "
         "AND a.effective_start_date <= b.effective_end_date AND b.effective_start_date <= a.effective_end_date"),
        ("scd_end_date_not_before_start_date", "dim_customer", "CRITICAL", f"SELECT COUNT(*) FROM {d}dim_customer WHERE effective_end_date < effective_start_date"),
        ("scd_no_gaps_between_versions", "dim_customer", "CRITICAL",
         f"SELECT COUNT(*) FROM (SELECT effective_end_date, LEAD(effective_start_date) OVER (PARTITION BY customer_id ORDER BY effective_start_date) AS nxt "
         f"FROM {d}dim_customer WHERE customer_id IS NOT NULL) WHERE nxt IS NOT NULL AND nxt <> effective_end_date + 1"),
        ("dim_customer_covers_every_oltp_customer", "dim_customer", "CRITICAL",
         f"SELECT ABS((SELECT COUNT(*) FROM {d}dim_customer WHERE is_current AND customer_id IS NOT NULL) - (SELECT COUNT(*) FROM sales.customers))"),
        ("fact_order_rows_equal_oltp_order_lines", "fact_order", "CRITICAL", f"SELECT ABS((SELECT COUNT(*) FROM {d}fact_order) - (SELECT COUNT(*) FROM sales.order_lines))"),
        ("fact_sale_rows_equal_oltp_invoice_lines", "fact_sale", "CRITICAL", f"SELECT ABS((SELECT COUNT(*) FROM {d}fact_sale) - (SELECT COUNT(*) FROM sales.invoice_lines))"),
        ("fact_order_grain_unique", "fact_order", "CRITICAL", f"SELECT COUNT(*) FROM (SELECT order_line_id FROM {d}fact_order GROUP BY 1 HAVING COUNT(*) > 1)"),
        ("fact_sale_grain_unique", "fact_sale", "CRITICAL", f"SELECT COUNT(*) FROM (SELECT invoice_line_id FROM {d}fact_sale GROUP BY 1 HAVING COUNT(*) > 1)"),
        ("fact_sale_total_matches_oltp", "fact_sale", "CRITICAL",
         f"SELECT CASE WHEN ABS((SELECT SUM(total_including_tax) FROM {d}fact_sale) - (SELECT SUM(wwi_dec2(ExtendedPrice)) FROM sales.invoice_lines)) > 0.005 THEN 1 ELSE 0 END"),
        ("fact_sale_profit_matches_oltp", "fact_sale", "CRITICAL",
         f"SELECT CASE WHEN ABS((SELECT SUM(profit) FROM {d}fact_sale) - (SELECT SUM(wwi_dec2(LineProfit)) FROM sales.invoice_lines)) > 0.005 THEN 1 ELSE 0 END"),
        ("fact_order_quantity_matches_oltp", "fact_order", "CRITICAL",
         f"SELECT CASE WHEN (SELECT SUM(ordered_quantity) FROM {d}fact_order) <> (SELECT SUM(wwi_int(Quantity)) FROM sales.order_lines) THEN 1 ELSE 0 END"),
        ("fact_order_total_equals_excl_plus_tax", "fact_order", "CRITICAL", f"SELECT COUNT(*) FROM {d}fact_order WHERE total_including_tax <> total_excluding_tax + tax_amount"),
        ("fact_order_customer_version_valid_on_order_date", "fact_order", "CRITICAL",
         f"SELECT COUNT(*) FROM {d}fact_order f JOIN {d}dim_customer c ON c.customer_key = f.customer_key JOIN {d}dim_date t ON t.date_key = f.order_date_key "
         "WHERE f.customer_key <> -1 AND NOT (t.full_date BETWEEN c.effective_start_date AND c.effective_end_date)"),
        ("fact_sale_customer_version_valid_on_invoice_date", "fact_sale", "CRITICAL",
         f"SELECT COUNT(*) FROM {d}fact_sale f JOIN {d}dim_customer c ON c.customer_key = f.customer_key JOIN {d}dim_date t ON t.date_key = f.invoice_date_key "
         "WHERE f.customer_key <> -1 AND NOT (t.full_date BETWEEN c.effective_start_date AND c.effective_end_date)"),
        ("fact_order_quantity_positive", "fact_order", "WARNING", f"SELECT COUNT(*) FROM {d}fact_order WHERE ordered_quantity <= 0"),
        ("fact_sale_quantity_positive", "fact_sale", "WARNING", f"SELECT COUNT(*) FROM {d}fact_sale WHERE quantity <= 0"),
    ]
    required = {"fact_order": ["customer_key", "city_key", "stock_item_key", "salesperson_key", "order_date_key"],
                "fact_sale": ["customer_key", "bill_to_customer_key", "city_key", "stock_item_key", "salesperson_key", "invoice_date_key"]}
    optional = {"fact_order": ["picker_key", "picked_date_key", "invoice_date_key"], "fact_sale": ["delivery_date_key"]}
    for fact, keys in required.items():
        for k in keys:
            c.append((f"{fact}.{k}_resolves_to_dimension", fact, "CRITICAL", f"SELECT COUNT(*) FROM {d}{fact} WHERE {k} = -1"))
    for fact, keys in optional.items():     # legitimately unknown (not picked / not invoiced / not delivered yet)
        for k in keys:
            c.append((f"{fact}.{k}_unknown_member_rows", fact, "INFO", f"SELECT COUNT(*) FROM {d}{fact} WHERE {k} = -1"))
    return c


def final_checks(ctx):
    results = [record_dq(ctx, "olap", name, table, sev, one(ctx, sql)) for name, table, sev, sql in olap_checks()]
    for table in COUNTED_TABLES:
        ctx.con.execute("INSERT INTO asb_olap.etl.table_counts VALUES (?,?,?,?)",
                        [ctx.run_id, ctx.load, table, one(ctx, f"SELECT COUNT(*) FROM asb_olap.{table}")])
    prev = ctx.con.execute("SELECT run_id FROM asb_olap.etl.pipeline_run WHERE load_no = ? AND status = 'SUCCESS' "
                           "ORDER BY started_at DESC LIMIT 1", [ctx.load]).fetchone()
    if prev:   # idempotency: the same load run again must give identical row counts
        diff = one(ctx, "SELECT COUNT(*) FROM asb_olap.etl.table_counts a JOIN asb_olap.etl.table_counts b "
                        "ON a.table_name = b.table_name WHERE a.run_id = ? AND b.run_id = ? AND a.row_count <> b.row_count",
                   [ctx.run_id, prev[0]])
        results.append(record_dq(ctx, "olap", f"rerun_row_counts_stable_vs_{prev[0]}", "all", "CRITICAL", diff))
    else:
        ctx.log.info("  (no earlier successful run of load %d to compare for the re-run check)", ctx.load)
    finish_dq(ctx, results, "OLAP checks")


# ----------------------------------------------------------------------------- step 9
def record_result(ctx):
    out = ROOT / "evidence" / ctx.run_id / "queries"
    out.mkdir(parents=True, exist_ok=True)
    queries = sorted(QUERY_SQL.glob("*.sql"))
    for q in queries:
        sql = strip_comments(q.read_text(encoding="utf-8")).strip().rstrip(";")
        ctx.con.execute(f"COPY ({sql}) TO '{(out / (q.stem + '.csv')).as_posix()}' (HEADER, DELIMITER ',')")
    ctx.log.info("  %d business queries exported to evidence/%s/queries", len(queries), ctx.run_id)


def export_etl_tables(ctx):
    out = ROOT / "evidence" / ctx.run_id
    out.mkdir(parents=True, exist_ok=True)
    for t in ("pipeline_run", "step_log", "ingestion_log", "table_counts", "dq_results"):
        ctx.con.execute(f"COPY (SELECT * FROM asb_olap.etl.{t} WHERE run_id = '{ctx.run_id}') TO '{(out / (t + '.csv')).as_posix()}' (HEADER, DELIMITER ',')")


# ----------------------------------------------------------------------------- main
STEPS = [
    ("Validate source files", validate_sources),
    ("Create / prepare OLTP database", prepare_oltp),
    ("Ingest CSV files into OLTP tables", ingest),
    ("Validate OLTP load", validate_oltp),
    ("Prepare OLAP schemas and staging", prepare_olap),
    ("Load dimensions (incl. SCD Type 2)", load_dimensions),
    ("Load facts", load_facts),
    ("Run final data-quality checks", final_checks),
    ("Record pipeline result", record_result),
]


def run_step(ctx, number, name, func):
    ctx.log.info("STEP %d/%d: %s", number, len(STEPS), name)
    started, status, message = datetime.now(), "SUCCESS", None
    try:
        func(ctx)
    except Exception as exc:          # noqa: BLE001 - logged, then re-raised
        status, message = "FAILED", str(exc)[:1500]
        raise
    finally:
        ctx.con.execute("INSERT INTO asb_olap.etl.step_log VALUES (?,?,?,?,?,?,?)",
                        [ctx.run_id, number, name, status, started, datetime.now(), message])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--load", type=int, choices=(1, 2), default=1, help="1 = initial build, 2 = second batch (SCD changes)")
    ap.add_argument("--effective-date", help="date the batch-2 changes take effect (default 2016-01-01)")
    ap.add_argument("--skip-ingest", action="store_true", help="load 1 only: keep the existing OLTP tables")
    args = ap.parse_args()
    os.chdir(ROOT)

    run_id = datetime.now().strftime("run_%Y%m%dT%H%M%S_") + uuid.uuid4().hex[:6]
    (ROOT / "logs").mkdir(exist_ok=True)
    log = logging.getLogger("pipe")
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S")
    for h in (logging.StreamHandler(), logging.FileHandler(ROOT / "logs" / f"{run_id}.log", encoding="utf-8")):
        h.setFormatter(fmt)
        log.addHandler(h)

    effective = args.effective_date or ("2016-01-01" if args.load == 2 else "1900-01-01")
    datetime.strptime(effective, "%Y-%m-%d")          # fail early on a bad date
    ctx = Ctx(con=open_db(), run_id=run_id, load=args.load, effective_date=effective, skip_ingest=args.skip_ingest, log=log)
    log.info("Pipeline run %s | load %d | effective date %s", run_id, ctx.load, ctx.effective_date)

    started, status, message = datetime.now(), "SUCCESS", None
    try:
        for number, (name, func) in enumerate(STEPS, start=1):
            run_step(ctx, number, name, func)
    except Exception as exc:              # noqa: BLE001
        status, message = "FAILED", str(exc)[:1500]
        log.error("PIPELINE FAILED: %s", exc)
    finally:
        ctx.con.execute("INSERT INTO asb_olap.etl.pipeline_run VALUES (?,?,?,?,?,?,?)",
                        [run_id, ctx.load, ctx.effective_date, started, datetime.now(), status, message])
        export_etl_tables(ctx)
        log.info("PIPELINE %s | log: logs/%s.log | evidence: evidence/%s/", status, run_id, run_id)
        ctx.con.close()
    return 0 if status == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
