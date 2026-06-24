# Data Dictionary — Bluestock Mutual Fund Analytics
**Capstone Project I — Mutual Fund Analytics**
**Day 2 Deliverable: Data Cleaning + SQL Database Design**

Database file: `bluestock_mf.db` (SQLite, star schema)
Schema DDL: `schema.sql`
Cleaned source CSVs: `data/processed/*.csv`

---

## 1. Schema Overview

A star schema with 2 dimension tables and 4 fact tables.

| Table | Type | Grain |
|---|---|---|
| `dim_fund` | Dimension | One row per mutual fund scheme (by AMFI code) |
| `dim_date` | Dimension | One row per calendar date present in any fact table |
| `fact_nav` | Fact | One row per fund per calendar day (daily NAV) |
| `fact_transactions` | Fact | One row per individual investor transaction |
| `fact_performance` | Fact | One row per fund per month-end (return metrics) |
| `fact_aum` | Fact | One row per fund per month-end (AUM snapshot) |

---

## 2. dim_fund

| Column | Type | Business Definition | Source |
|---|---|---|---|
| `fund_key` | INTEGER (PK) | Surrogate key, auto-incremented | Generated on load |
| `amfi_code` | INTEGER (Natural Key, Unique) | AMFI scheme code uniquely identifying a mutual fund scheme | Fund master reference data |
| `scheme_name` | TEXT | Full name of the mutual fund scheme | Fund master reference data |
| `fund_house` | TEXT | Asset Management Company (AMC) operating the fund (e.g. HDFC, SBI, Axis) | Fund master reference data |
| `category` | TEXT | SEBI fund category (e.g. Large Cap, Mid Cap, ELSS, Debt - Short Duration) | Fund master reference data |
| `plan_type` | TEXT | `Direct` or `Regular` plan | Fund master reference data |
| `launch_date` | TEXT (date, `YYYY-MM-DD`) | Date the scheme was launched | Fund master reference data |

---

## 3. dim_date

| Column | Type | Business Definition |
|---|---|---|
| `date_key` | INTEGER (PK) | Surrogate key in `YYYYMMDD` integer format |
| `full_date` | TEXT (date, `YYYY-MM-DD`, Unique) | Calendar date |
| `year` | INTEGER | Calendar year |
| `quarter` | INTEGER | Calendar quarter (1–4) |
| `month` | INTEGER | Calendar month (1–12) |
| `month_name` | TEXT | Full month name (e.g. "January") |
| `day` | INTEGER | Day of month |
| `day_of_week` | TEXT | Full weekday name (e.g. "Monday") |
| `is_weekend` | INTEGER (0/1) | 1 if Saturday/Sunday |
| `is_month_end` | INTEGER (0/1) | 1 if the last calendar day of the month |

---

## 4. fact_nav — Daily NAV History

Source file: `nav_history.csv` → cleaned to `data/processed/nav_history_clean.csv`

| Column | Type | Business Definition | Source / Cleaning Applied |
|---|---|---|---|
| `nav_key` | INTEGER (PK) | Surrogate key | Generated on load |
| `fund_key` | INTEGER (FK → dim_fund) | Links to the fund | Mapped from `amfi_code` |
| `date_key` | INTEGER (FK → dim_date) | Links to the NAV date | Mapped from `nav_date` |
| `nav` | REAL, `CHECK (nav > 0)` | Net Asset Value of the fund unit on that date (₹) | Raw `nav`; mixed date formats parsed; missing values forward-filled per fund (then back-filled for leading gaps); values ≤ 0 treated as missing and filled; exact duplicate (fund, date) rows removed |

**Cleaning rules applied:** parsed `nav_date` from mixed formats (`YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY`); sorted by `amfi_code`, `nav_date`; forward-filled missing/invalid NAV per fund to cover holidays/weekends; removed duplicate `(amfi_code, nav_date)` rows; enforced `nav > 0`.

---

## 5. fact_transactions — Investor Transactions

Source file: `investor_transactions.csv` → cleaned to `data/processed/investor_transactions_clean.csv`

| Column | Type | Business Definition | Source / Cleaning Applied |
|---|---|---|---|
| `transaction_key` | INTEGER (PK) | Surrogate key | Generated on load |
| `transaction_id` | TEXT (Unique) | Unique transaction identifier | Raw `transaction_id`; deduplicated |
| `investor_id` | TEXT | Unique identifier for the investor | Raw `investor_id` |
| `fund_key` | INTEGER (FK → dim_fund) | Links to the fund involved | Mapped from `amfi_code` |
| `date_key` | INTEGER (FK → dim_date) | Links to the transaction date | Mapped from `transaction_date` |
| `transaction_type` | TEXT, `CHECK IN ('SIP','Lumpsum','Redemption')` | Type of investment transaction | Standardised from free-form values (`sip`, `SIP`, `S.I.P.` → `SIP`; `lump sum`, `LUMPSUM` → `Lumpsum`; `redeem`, `REDEMPTION` → `Redemption`) |
| `amount` | REAL, `CHECK (amount > 0)` | Transaction amount in ₹ | Validated `amount > 0`; negative/zero rows dropped |
| `kyc_status` | TEXT, `CHECK IN ('Verified','Pending','Rejected')` | Investor's KYC compliance status at time of transaction | Standardised enum (`verified`, `KYC Verified` → `Verified`, etc.) |
| `state` | TEXT | Indian state of the investor | Raw `state` |

**Cleaning rules applied:** standardised `transaction_type` to 3 canonical values; standardised `kyc_status` to 3 canonical enum values; parsed mixed date formats; validated `amount > 0`; removed duplicate `transaction_id` rows.

---

## 6. fact_performance — Monthly Scheme Performance

Source file: `scheme_performance.csv` → cleaned to `data/processed/scheme_performance_clean.csv`

| Column | Type | Business Definition | Source / Cleaning Applied |
|---|---|---|---|
| `performance_key` | INTEGER (PK) | Surrogate key | Generated on load |
| `fund_key` | INTEGER (FK → dim_fund) | Links to the fund | Mapped from `amfi_code` |
| `date_key` | INTEGER (FK → dim_date) | Links to the month-end reporting date | Mapped from `period_end_date` |
| `returns_1y_pct` | REAL | Trailing 1-year return (%) | Raw `returns_1y_pct`; coerced to numeric, non-numeric values (e.g. `"N/A"`) dropped |
| `returns_3y_pct` | REAL | Trailing 3-year return (%) | Coerced to numeric |
| `returns_5y_pct` | REAL | Trailing 5-year return (%) | Coerced to numeric |
| `expense_ratio_pct` | REAL | Annual expense ratio (%) charged by the fund | Raw `expense_ratio_pct`; validity checked against 0.1%–2.5% band |
| `is_return_anomaly` | INTEGER (0/1) | Flag: 1 if any return value falls outside a plausible range (< -80% or > 150%) | Derived during cleaning |
| `is_expense_ratio_out_of_range` | INTEGER (0/1) | Flag: 1 if `expense_ratio_pct` falls outside the valid 0.1%–2.5% regulatory band | Derived during cleaning |

**Cleaning rules applied:** coerced return columns to numeric (non-numeric/missing rows dropped); flagged (not dropped) statistical anomalies in returns; flagged (not dropped) out-of-range expense ratios so analysts can audit them; parsed dates; removed duplicate `(amfi_code, period_end_date)` rows.

---

## 7. fact_aum — Monthly AUM Snapshot

Source file: `scheme_performance.csv` (the `aum_cr` column) → cleaned to `data/processed/scheme_performance_clean.csv`

| Column | Type | Business Definition | Source / Cleaning Applied |
|---|---|---|---|
| `aum_key` | INTEGER (PK) | Surrogate key | Generated on load |
| `fund_key` | INTEGER (FK → dim_fund) | Links to the fund | Mapped from `amfi_code` |
| `date_key` | INTEGER (FK → dim_date) | Links to the month-end snapshot date | Mapped from `period_end_date` |
| `aum_cr` | REAL, `CHECK (aum_cr > 0)` | Assets Under Management, in ₹ Crores | Raw `aum_cr` from the scheme performance file |

---

## 8. Data Quality Notes / Known Limitations

- `fact_performance` and `fact_aum` are both sourced from `scheme_performance.csv` since AUM is reported alongside return metrics at month-end; they are split into separate fact tables to match the star schema design (performance metrics vs. AUM are conceptually distinct facts and may evolve independently in future loads).
- Rows flagged `is_return_anomaly = 1` or `is_expense_ratio_out_of_range = 1` are **retained, not deleted** — flagging preserves auditability while letting analysts choose whether to exclude them from specific analyses.
- `fact_nav` includes only trading days; stray weekend rows present in the raw extract were not explicitly dropped but are naturally absorbed into the daily series via forward-fill logic if present.
- See `cleaning_log.txt` (generated by `clean_data.py`) for exact row-count deltas at each cleaning step.

---

## 9. File Inventory

| File | Description |
|---|---|
| `data/processed/nav_history_clean.csv` | Cleaned daily NAV history |
| `data/processed/investor_transactions_clean.csv` | Cleaned investor transactions |
| `data/processed/scheme_performance_clean.csv` | Cleaned scheme performance + AUM |
| `data/raw/_fund_master_reference.csv` | Fund master / dim_fund source reference |
| `bluestock_mf.db` | SQLite database with the full star schema, loaded |
| `schema.sql` | DDL for all 6 tables + indexes |
| `queries.sql` | 10 analytical SQL queries |
| `data_dictionary.md` | This file |
