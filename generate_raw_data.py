"""
Generates realistic-but-messy synthetic mutual fund data for the
Capstone Project I - Mutual Fund Analytics (Day 2 task).

Produces three RAW (dirty) CSVs in data/raw/:
  - nav_history.csv
  - investor_transactions.csv
  - scheme_performance.csv

Deliberately injects the kinds of issues the task asks you to clean:
  - duplicate rows
  - missing NAV values on some dates (to be forward-filled)
  - mixed date formats
  - inconsistent transaction_type strings (SIP/sip/Lumpsum/LUMP SUM/Redemption/redeem)
  - inconsistent KYC status values
  - a few negative/zero NAV and amount values
  - expense ratios outside the valid 0.1%-2.5% band
  - non-numeric return values
"""
import numpy as np
import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

# -----------------------------------------------------------------
# 1. Master fund list (this is the "source of truth" dim_fund data)
# -----------------------------------------------------------------
fund_houses = ["HDFC", "ICICI Pru", "SBI", "Axis", "Kotak", "Nippon India", "UTI", "Aditya Birla SL", "Mirae Asset", "DSP"]
categories = ["Large Cap", "Mid Cap", "Small Cap", "Flexi Cap", "ELSS", "Debt - Short Duration", "Hybrid - Aggressive", "Index Fund", "Multi Cap", "Focused"]
plan_types = ["Direct", "Regular"]

funds = []
amfi_start = 100001
for i in range(25):
    house = fund_houses[i % len(fund_houses)]
    cat = categories[i % len(categories)]
    plan = plan_types[i % len(plan_types)]
    amfi_code = amfi_start + i
    scheme_name = f"{house} {cat} Fund - {plan} Plan"
    launch_date = datetime(2015, 1, 1) + timedelta(days=random.randint(0, 2500))
    funds.append({
        "amfi_code": amfi_code,
        "scheme_name": scheme_name,
        "fund_house": house,
        "category": cat,
        "plan_type": plan,
        "launch_date": launch_date.strftime("%Y-%m-%d"),
    })
funds_df = pd.DataFrame(funds)
funds_df.to_csv("data/raw/_fund_master_reference.csv", index=False)  # reference only, not a deliverable

# -----------------------------------------------------------------
# 2. nav_history.csv  (messy)
# -----------------------------------------------------------------
start_date = datetime(2024, 1, 1)
end_date = datetime(2026, 6, 23)
all_days = pd.date_range(start_date, end_date, freq="D")  # includes weekends on purpose (dirty)

nav_rows = []
date_fmts = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"]

for f in funds:
    base_nav = np.random.uniform(15, 250)
    nav = base_nav
    for d in all_days:
        is_weekend = d.weekday() >= 5
        # Skip ~most weekends (real markets closed) but leave a few stray weekend rows (dirty)
        if is_weekend and random.random() > 0.03:
            continue
        # daily NAV random walk
        nav = max(0.5, nav * (1 + np.random.normal(0.0003, 0.008)))
        nav_val = round(nav, 4)

        # inject missing NAV (~2% of rows) -- to be forward-filled later
        if random.random() < 0.02:
            nav_val = np.nan

        # inject a few invalid NAVs (negative/zero) (~0.3%)
        if random.random() < 0.003:
            nav_val = round(-abs(nav_val if not np.isnan(nav_val) else 1.0), 4)

        fmt = random.choice(date_fmts)
        nav_rows.append({
            "amfi_code": f["amfi_code"],
            "scheme_name": f["scheme_name"],
            "nav_date": d.strftime(fmt),
            "nav": nav_val,
        })

nav_df = pd.DataFrame(nav_rows)
# inject duplicate rows (~1%)
dupes = nav_df.sample(frac=0.01, random_state=1)
nav_df = pd.concat([nav_df, dupes], ignore_index=True)
# shuffle to make it realistically unsorted
nav_df = nav_df.sample(frac=1, random_state=2).reset_index(drop=True)
nav_df.to_csv("data/raw/nav_history.csv", index=False)

# -----------------------------------------------------------------
# 3. investor_transactions.csv  (messy)
# -----------------------------------------------------------------
txn_type_variants = {
    "SIP": ["SIP", "sip", "Sip", "S.I.P."],
    "Lumpsum": ["Lumpsum", "LUMPSUM", "Lump Sum", "lump sum"],
    "Redemption": ["Redemption", "REDEMPTION", "redeem", "Redeem"],
}
kyc_variants = {
    "Verified": ["Verified", "VERIFIED", "verified", "KYC Verified"],
    "Pending": ["Pending", "PENDING", "pending"],
    "Rejected": ["Rejected", "REJECTED", "rejected"],
}
states = ["Maharashtra", "Tamil Nadu", "Karnataka", "Delhi", "Gujarat", "West Bengal",
          "Telangana", "Uttar Pradesh", "Rajasthan", "Kerala"]

txn_rows = []
for i in range(15000):
    f = random.choice(funds)
    txn_date = start_date + timedelta(days=random.randint(0, (end_date - start_date).days))
    canon_type = random.choices(list(txn_type_variants.keys()), weights=[0.55, 0.30, 0.15])[0]
    type_str = random.choice(txn_type_variants[canon_type])
    canon_kyc = random.choices(list(kyc_variants.keys()), weights=[0.85, 0.10, 0.05])[0]
    kyc_str = random.choice(kyc_variants[canon_kyc])

    if canon_type == "SIP":
        amount = round(np.random.uniform(500, 25000), 2)
    elif canon_type == "Lumpsum":
        amount = round(np.random.uniform(5000, 500000), 2)
    else:
        amount = round(np.random.uniform(1000, 300000), 2)

    # inject a few invalid amounts (~0.5%)
    if random.random() < 0.005:
        amount = round(-amount, 2)

    fmt = random.choice(date_fmts)
    txn_rows.append({
        "transaction_id": f"TXN{100000+i}",
        "investor_id": f"INV{random.randint(1000, 4999)}",
        "amfi_code": f["amfi_code"],
        "transaction_type": type_str,
        "amount": amount,
        "transaction_date": txn_date.strftime(fmt),
        "kyc_status": kyc_str,
        "state": random.choice(states),
    })

txn_df = pd.DataFrame(txn_rows)
dupes = txn_df.sample(frac=0.008, random_state=3)
txn_df = pd.concat([txn_df, dupes], ignore_index=True)
txn_df = txn_df.sample(frac=1, random_state=4).reset_index(drop=True)
txn_df.to_csv("data/raw/investor_transactions.csv", index=False)

# -----------------------------------------------------------------
# 4. scheme_performance.csv  (messy)
# -----------------------------------------------------------------
perf_rows = []
month_starts = pd.date_range(start_date, end_date, freq="MS")
for f in funds:
    aum = np.random.uniform(200, 15000)  # crores
    for m in month_starts:
        aum = max(50, aum * (1 + np.random.normal(0.01, 0.04)))
        ret_1y = np.random.normal(12, 8)
        ret_3y = np.random.normal(14, 6)
        ret_5y = np.random.normal(13, 5)
        expense_ratio = round(np.random.uniform(0.3, 2.1), 2)

        # inject out-of-range expense ratios (~3%)
        if random.random() < 0.03:
            expense_ratio = round(random.choice([np.random.uniform(2.6, 4.0), np.random.uniform(0.0, 0.09)]), 2)

        # inject non-numeric return values (~1.5%)
        ret_1y_val = round(ret_1y, 2)
        if random.random() < 0.015:
            ret_1y_val = "N/A"

        perf_rows.append({
            "amfi_code": f["amfi_code"],
            "period_end_date": m.strftime(random.choice(date_fmts)),
            "returns_1y_pct": ret_1y_val,
            "returns_3y_pct": round(ret_3y, 2),
            "returns_5y_pct": round(ret_5y, 2),
            "expense_ratio_pct": expense_ratio,
            "aum_cr": round(aum, 2),
        })

perf_df = pd.DataFrame(perf_rows)
dupes = perf_df.sample(frac=0.01, random_state=5)
perf_df = pd.concat([perf_df, dupes], ignore_index=True)
perf_df = perf_df.sample(frac=1, random_state=6).reset_index(drop=True)
perf_df.to_csv("data/raw/scheme_performance.csv", index=False)

print("nav_history.csv:", len(nav_df), "rows")
print("investor_transactions.csv:", len(txn_df), "rows")
print("scheme_performance.csv:", len(perf_df), "rows")
print("funds:", len(funds))
