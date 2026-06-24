"""
Day 2: Data Cleaning
Cleans the three raw CSVs and writes cleaned versions to data/processed/.

Cleaning rules implemented (per task spec):

nav_history.csv:
  - parse nav_date -> datetime (handles mixed formats)
  - sort by amfi_code, nav_date
  - forward-fill missing NAV per fund (holidays/weekends)
  - remove duplicate rows
  - validate nav > 0 (drop/flag invalid rows)

investor_transactions.csv:
  - standardise transaction_type -> {SIP, Lumpsum, Redemption}
  - validate amount > 0
  - fix transaction_date formats -> datetime
  - check kyc_status against allowed enum {Verified, Pending, Rejected}

scheme_performance.csv:
  - validate returns_1y/3y/5y are numeric (coerce, flag non-numeric)
  - flag anomalies (extreme outlier returns)
  - check expense_ratio_pct is within 0.1% - 2.5%; flag/clip out-of-range
"""
import numpy as np
import pandas as pd

LOG = []  # cleaning audit log


def log(msg):
    print(msg)
    LOG.append(msg)


# -------------------------------------------------------------------
# 1. NAV HISTORY
# -------------------------------------------------------------------
def clean_nav_history(path_in, path_out):
    df = pd.read_csv(path_in)
    raw_rows = len(df)

    # Parse mixed date formats robustly
    df["nav_date"] = pd.to_datetime(df["nav_date"], dayfirst=True, errors="coerce", format="mixed")
    bad_dates = df["nav_date"].isna().sum()
    df = df.dropna(subset=["nav_date"])

    # Remove exact duplicate rows
    before = len(df)
    df = df.drop_duplicates(subset=["amfi_code", "nav_date"], keep="first")
    dupes_removed = before - len(df)

    # Sort by amfi_code, nav_date (required before forward-fill)
    df = df.sort_values(["amfi_code", "nav_date"]).reset_index(drop=True)

    # Invalid NAV (<=0) -> set to NaN so they get forward-filled, then flag
    invalid_nav = (df["nav"] <= 0).sum()
    df.loc[df["nav"] <= 0, "nav"] = np.nan

    missing_before = df["nav"].isna().sum()

    # Forward-fill missing NAV per fund (handles holidays/weekends + invalid values)
    df["nav"] = df.groupby("amfi_code")["nav"].ffill()
    # Any remaining NaN at the very start of a series -> back-fill as last resort
    df["nav"] = df.groupby("amfi_code")["nav"].bfill()
    df["nav"] = df["nav"].round(4)

    still_missing = df["nav"].isna().sum()
    df = df.dropna(subset=["nav"])

    df = df.rename(columns={"nav_date": "nav_date"})
    df = df[["amfi_code", "scheme_name", "nav_date", "nav"]]
    df["nav_date"] = df["nav_date"].dt.strftime("%Y-%m-%d")

    df.to_csv(path_out, index=False)

    log(f"[nav_history] raw_rows={raw_rows} -> clean_rows={len(df)} | "
        f"unparseable_dates_dropped={bad_dates} | duplicates_removed={dupes_removed} | "
        f"invalid_nav(<=0)_flagged_and_filled={invalid_nav} | rows_dropped_unfillable={still_missing}")
    return df


# -------------------------------------------------------------------
# 2. INVESTOR TRANSACTIONS
# -------------------------------------------------------------------
TXN_TYPE_MAP = {
    "sip": "SIP", "s.i.p.": "SIP",
    "lumpsum": "Lumpsum", "lump sum": "Lumpsum",
    "redemption": "Redemption", "redeem": "Redemption",
}
KYC_ALLOWED = {"Verified", "Pending", "Rejected"}
KYC_MAP = {
    "verified": "Verified", "kyc verified": "Verified",
    "pending": "Pending",
    "rejected": "Rejected",
}


def clean_investor_transactions(path_in, path_out):
    df = pd.read_csv(path_in)
    raw_rows = len(df)

    # Standardise transaction_type
    df["transaction_type"] = (
        df["transaction_type"].str.strip().str.lower().map(TXN_TYPE_MAP)
    )
    unmapped_type = df["transaction_type"].isna().sum()
    df = df.dropna(subset=["transaction_type"])

    # Standardise kyc_status
    df["kyc_status"] = df["kyc_status"].str.strip().str.lower().map(KYC_MAP)
    unmapped_kyc = df["kyc_status"].isna().sum()
    df = df.dropna(subset=["kyc_status"])
    assert set(df["kyc_status"].unique()).issubset(KYC_ALLOWED)

    # Fix transaction_date formats
    df["transaction_date"] = pd.to_datetime(
        df["transaction_date"], dayfirst=True, errors="coerce", format="mixed"
    )
    bad_dates = df["transaction_date"].isna().sum()
    df = df.dropna(subset=["transaction_date"])

    # Validate amount > 0
    invalid_amount = (df["amount"] <= 0).sum()
    df = df[df["amount"] > 0]

    # Remove duplicate transaction_ids
    before = len(df)
    df = df.drop_duplicates(subset=["transaction_id"], keep="first")
    dupes_removed = before - len(df)

    df["transaction_date"] = df["transaction_date"].dt.strftime("%Y-%m-%d")
    df = df[["transaction_id", "investor_id", "amfi_code", "transaction_type",
              "amount", "transaction_date", "kyc_status", "state"]]

    df.to_csv(path_out, index=False)

    log(f"[investor_transactions] raw_rows={raw_rows} -> clean_rows={len(df)} | "
        f"unmapped_transaction_type_dropped={unmapped_type} | unmapped_kyc_dropped={unmapped_kyc} | "
        f"unparseable_dates_dropped={bad_dates} | invalid_amount(<=0)_dropped={invalid_amount} | "
        f"duplicate_txn_ids_removed={dupes_removed}")
    return df


# -------------------------------------------------------------------
# 3. SCHEME PERFORMANCE
# -------------------------------------------------------------------
def clean_scheme_performance(path_in, path_out):
    df = pd.read_csv(path_in)
    raw_rows = len(df)

    # Coerce numeric return columns; non-numeric -> NaN
    for col in ["returns_1y_pct", "returns_3y_pct", "returns_5y_pct"]:
        non_numeric = pd.to_numeric(df[col], errors="coerce").isna().sum() - df[col].isna().sum()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        log(f"[scheme_performance] {col}: non_numeric_values_coerced_to_NaN={non_numeric}")

    before = len(df)
    df = df.dropna(subset=["returns_1y_pct", "returns_3y_pct", "returns_5y_pct"])
    log(f"[scheme_performance] rows dropped for missing/non-numeric returns: {before - len(df)}")

    # Flag anomalies: returns outside a sane band (e.g. -80% to +150%)
    anomaly_mask = (
        (df["returns_1y_pct"] < -80) | (df["returns_1y_pct"] > 150) |
        (df["returns_3y_pct"] < -80) | (df["returns_3y_pct"] > 150) |
        (df["returns_5y_pct"] < -80) | (df["returns_5y_pct"] > 150)
    )
    df["is_return_anomaly"] = anomaly_mask
    log(f"[scheme_performance] flagged return anomalies (kept, flagged): {anomaly_mask.sum()}")

    # Validate expense_ratio_pct within 0.1% - 2.5%; flag out-of-range, clip for loading
    out_of_range = ((df["expense_ratio_pct"] < 0.1) | (df["expense_ratio_pct"] > 2.5)).sum()
    df["is_expense_ratio_out_of_range"] = (df["expense_ratio_pct"] < 0.1) | (df["expense_ratio_pct"] > 2.5)
    log(f"[scheme_performance] expense_ratio_pct out of valid range (0.1-2.5) flagged: {out_of_range}")

    # Parse date, dedupe
    df["period_end_date"] = pd.to_datetime(df["period_end_date"], dayfirst=True, errors="coerce", format="mixed")
    bad_dates = df["period_end_date"].isna().sum()
    df = df.dropna(subset=["period_end_date"])

    before = len(df)
    df = df.drop_duplicates(subset=["amfi_code", "period_end_date"], keep="first")
    dupes_removed = before - len(df)

    df["period_end_date"] = df["period_end_date"].dt.strftime("%Y-%m-%d")
    df = df[["amfi_code", "period_end_date", "returns_1y_pct", "returns_3y_pct", "returns_5y_pct",
              "expense_ratio_pct", "aum_cr", "is_return_anomaly", "is_expense_ratio_out_of_range"]]

    df.to_csv(path_out, index=False)

    log(f"[scheme_performance] raw_rows={raw_rows} -> clean_rows={len(df)} | "
        f"unparseable_dates_dropped={bad_dates} | duplicates_removed={dupes_removed}")
    return df


if __name__ == "__main__":
    nav = clean_nav_history("data/raw/nav_history.csv", "data/processed/nav_history_clean.csv")
    txn = clean_investor_transactions("data/raw/investor_transactions.csv", "data/processed/investor_transactions_clean.csv")
    perf = clean_scheme_performance("data/raw/scheme_performance.csv", "data/processed/scheme_performance_clean.csv")

    with open("data/processed/cleaning_log.txt", "w") as f:
        f.write("\n".join(LOG))

    print("\n--- FINAL CLEAN ROW COUNTS ---")
    print("nav_history_clean:", len(nav))
    print("investor_transactions_clean:", len(txn))
    print("scheme_performance_clean:", len(perf))
