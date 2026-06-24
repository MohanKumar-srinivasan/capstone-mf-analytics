"""
Day 2: Load all cleaned datasets into SQLite (bluestock_mf.db)
using SQLAlchemy create_engine + df.to_sql(), per the star schema
defined in schema.sql.

Steps:
  1. Create the DB and apply schema.sql (DDL).
  2. Build dim_fund from the fund master reference.
  3. Build dim_date by collecting every distinct date across all facts.
  4. Load fact_nav, fact_transactions, fact_performance, fact_aum,
     mapping natural keys (amfi_code, date) -> surrogate keys
     (fund_key, date_key) before insert.
  5. Verify row counts match the source (cleaned) CSVs.
"""
import sqlite3
import pandas as pd
from sqlalchemy import create_engine

DB_PATH = "bluestock_mf.db"
engine = create_engine(f"sqlite:///{DB_PATH}")

# ------------------------------------------------------------------
# 1. (Re)create schema
# ------------------------------------------------------------------
with open("schema.sql") as f:
    ddl = f.read()

raw_conn = sqlite3.connect(DB_PATH)
raw_conn.executescript(ddl)
raw_conn.commit()
raw_conn.close()

# ------------------------------------------------------------------
# 2. dim_fund
# ------------------------------------------------------------------
fund_master = pd.read_csv("data/raw/_fund_master_reference.csv")
fund_master.to_sql("dim_fund", engine, if_exists="append", index=False,
                    method="multi",
                    dtype=None)

dim_fund_lookup = pd.read_sql("SELECT fund_key, amfi_code FROM dim_fund", engine)
amfi_to_key = dict(zip(dim_fund_lookup["amfi_code"], dim_fund_lookup["fund_key"]))

# ------------------------------------------------------------------
# 3. Read cleaned facts
# ------------------------------------------------------------------
nav = pd.read_csv("data/processed/nav_history_clean.csv", parse_dates=["nav_date"])
txn = pd.read_csv("data/processed/investor_transactions_clean.csv", parse_dates=["transaction_date"])
perf = pd.read_csv("data/processed/scheme_performance_clean.csv", parse_dates=["period_end_date"])

# ------------------------------------------------------------------
# 4. Build dim_date from the union of all dates used in the facts
# ------------------------------------------------------------------
all_dates = pd.concat([
    nav["nav_date"],
    txn["transaction_date"],
    perf["period_end_date"],
]).drop_duplicates().sort_values().reset_index(drop=True)

dim_date = pd.DataFrame({"full_date": all_dates})
dim_date["date_key"] = dim_date["full_date"].dt.strftime("%Y%m%d").astype(int)
dim_date["year"] = dim_date["full_date"].dt.year
dim_date["quarter"] = dim_date["full_date"].dt.quarter
dim_date["month"] = dim_date["full_date"].dt.month
dim_date["month_name"] = dim_date["full_date"].dt.month_name()
dim_date["day"] = dim_date["full_date"].dt.day
dim_date["day_of_week"] = dim_date["full_date"].dt.day_name()
dim_date["is_weekend"] = dim_date["full_date"].dt.weekday.isin([5, 6]).astype(int)
dim_date["is_month_end"] = dim_date["full_date"].dt.is_month_end.astype(int)
dim_date["full_date"] = dim_date["full_date"].dt.strftime("%Y-%m-%d")
dim_date = dim_date[["date_key", "full_date", "year", "quarter", "month",
                     "month_name", "day", "day_of_week", "is_weekend", "is_month_end"]]

dim_date.to_sql("dim_date", engine, if_exists="append", index=False, method="multi", chunksize=1000)

date_to_key = dict(zip(pd.to_datetime(dim_date["full_date"]), dim_date["date_key"]))

# ------------------------------------------------------------------
# 5. fact_nav
# ------------------------------------------------------------------
fact_nav = pd.DataFrame({
    "fund_key": nav["amfi_code"].map(amfi_to_key),
    "date_key": nav["nav_date"].map(date_to_key),
    "nav": nav["nav"],
})
fact_nav.to_sql("fact_nav", engine, if_exists="append", index=False, method="multi", chunksize=2000)

# ------------------------------------------------------------------
# 6. fact_transactions
# ------------------------------------------------------------------
fact_txn = pd.DataFrame({
    "transaction_id": txn["transaction_id"],
    "investor_id": txn["investor_id"],
    "fund_key": txn["amfi_code"].map(amfi_to_key),
    "date_key": txn["transaction_date"].map(date_to_key),
    "transaction_type": txn["transaction_type"],
    "amount": txn["amount"],
    "kyc_status": txn["kyc_status"],
    "state": txn["state"],
})
fact_txn.to_sql("fact_transactions", engine, if_exists="append", index=False, method="multi", chunksize=2000)

# ------------------------------------------------------------------
# 7. fact_performance
# ------------------------------------------------------------------
fact_perf = pd.DataFrame({
    "fund_key": perf["amfi_code"].map(amfi_to_key),
    "date_key": perf["period_end_date"].map(date_to_key),
    "returns_1y_pct": perf["returns_1y_pct"],
    "returns_3y_pct": perf["returns_3y_pct"],
    "returns_5y_pct": perf["returns_5y_pct"],
    "expense_ratio_pct": perf["expense_ratio_pct"],
    "is_return_anomaly": perf["is_return_anomaly"].astype(int),
    "is_expense_ratio_out_of_range": perf["is_expense_ratio_out_of_range"].astype(int),
})
fact_perf.to_sql("fact_performance", engine, if_exists="append", index=False, method="multi", chunksize=2000)

# ------------------------------------------------------------------
# 8. fact_aum (derived from scheme_performance aum_cr column)
# ------------------------------------------------------------------
fact_aum = pd.DataFrame({
    "fund_key": perf["amfi_code"].map(amfi_to_key),
    "date_key": perf["period_end_date"].map(date_to_key),
    "aum_cr": perf["aum_cr"],
})
fact_aum.to_sql("fact_aum", engine, if_exists="append", index=False, method="multi", chunksize=2000)

# ------------------------------------------------------------------
# 9. Verify row counts match source cleaned CSVs
# ------------------------------------------------------------------
print("\n--- ROW COUNT VERIFICATION (source CSV vs loaded table) ---")
checks = [
    ("dim_fund", len(fund_master), "dim_fund"),
    ("nav_history_clean.csv", len(nav), "fact_nav"),
    ("investor_transactions_clean.csv", len(txn), "fact_transactions"),
    ("scheme_performance_clean.csv (perf)", len(perf), "fact_performance"),
    ("scheme_performance_clean.csv (aum)", len(perf), "fact_aum"),
]
with engine.connect() as conn:
    for label, src_count, table in checks:
        db_count = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {table}").scalar()
        status = "OK" if src_count == db_count else "MISMATCH"
        print(f"{label:42s} source={src_count:>6} | db={db_count:>6} | {status}")

print("\nLoad complete ->", DB_PATH)
