-- ============================================================
-- Bluestock Mutual Fund Analytics — SQLite Star Schema
-- Day 2: Data Cleaning + SQL Database Design
-- ============================================================
-- Grain:
--   fact_nav         : one row per fund per calendar day
--   fact_transactions: one row per investor transaction
--   fact_performance : one row per fund per month-end
--   fact_aum         : one row per fund per month-end (AUM snapshot)
-- ============================================================

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fact_aum;
DROP TABLE IF EXISTS fact_performance;
DROP TABLE IF EXISTS fact_transactions;
DROP TABLE IF EXISTS fact_nav;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_fund;

-- ------------------------------------------------------------
-- DIMENSION: dim_fund
-- ------------------------------------------------------------
CREATE TABLE dim_fund (
    fund_key      INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code     INTEGER NOT NULL UNIQUE,
    scheme_name   TEXT NOT NULL,
    fund_house    TEXT,
    category      TEXT,
    plan_type     TEXT,
    launch_date   TEXT
);

-- ------------------------------------------------------------
-- DIMENSION: dim_date
-- One row per calendar date that appears anywhere in the facts.
-- ------------------------------------------------------------
CREATE TABLE dim_date (
    date_key      INTEGER PRIMARY KEY,      -- YYYYMMDD integer surrogate key
    full_date     TEXT NOT NULL UNIQUE,      -- 'YYYY-MM-DD'
    year          INTEGER NOT NULL,
    quarter       INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    month_name    TEXT NOT NULL,
    day           INTEGER NOT NULL,
    day_of_week   TEXT NOT NULL,
    is_weekend    INTEGER NOT NULL,          -- 0/1
    is_month_end  INTEGER NOT NULL           -- 0/1
);

-- ------------------------------------------------------------
-- FACT: fact_nav  (daily NAV per fund)
-- ------------------------------------------------------------
CREATE TABLE fact_nav (
    nav_key       INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_key      INTEGER NOT NULL,
    date_key      INTEGER NOT NULL,
    nav           REAL NOT NULL CHECK (nav > 0),
    FOREIGN KEY (fund_key) REFERENCES dim_fund (fund_key),
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key),
    UNIQUE (fund_key, date_key)
);

-- ------------------------------------------------------------
-- FACT: fact_transactions  (investor-level transactions)
-- ------------------------------------------------------------
CREATE TABLE fact_transactions (
    transaction_key   INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id    TEXT NOT NULL UNIQUE,
    investor_id       TEXT NOT NULL,
    fund_key          INTEGER NOT NULL,
    date_key          INTEGER NOT NULL,
    transaction_type  TEXT NOT NULL CHECK (transaction_type IN ('SIP', 'Lumpsum', 'Redemption')),
    amount            REAL NOT NULL CHECK (amount > 0),
    kyc_status        TEXT NOT NULL CHECK (kyc_status IN ('Verified', 'Pending', 'Rejected')),
    state             TEXT,
    FOREIGN KEY (fund_key) REFERENCES dim_fund (fund_key),
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key)
);

-- ------------------------------------------------------------
-- FACT: fact_performance  (monthly return metrics per fund)
-- ------------------------------------------------------------
CREATE TABLE fact_performance (
    performance_key             INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_key                    INTEGER NOT NULL,
    date_key                    INTEGER NOT NULL,
    returns_1y_pct              REAL,
    returns_3y_pct              REAL,
    returns_5y_pct              REAL,
    expense_ratio_pct           REAL,
    is_return_anomaly           INTEGER NOT NULL DEFAULT 0,
    is_expense_ratio_out_of_range INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (fund_key) REFERENCES dim_fund (fund_key),
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key),
    UNIQUE (fund_key, date_key)
);

-- ------------------------------------------------------------
-- FACT: fact_aum  (monthly AUM snapshot per fund)
-- ------------------------------------------------------------
CREATE TABLE fact_aum (
    aum_key       INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_key      INTEGER NOT NULL,
    date_key      INTEGER NOT NULL,
    aum_cr        REAL NOT NULL CHECK (aum_cr > 0),
    FOREIGN KEY (fund_key) REFERENCES dim_fund (fund_key),
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key),
    UNIQUE (fund_key, date_key)
);

-- ------------------------------------------------------------
-- Helpful indexes for analytical query performance
-- ------------------------------------------------------------
CREATE INDEX idx_fact_nav_date ON fact_nav (date_key);
CREATE INDEX idx_fact_txn_fund ON fact_transactions (fund_key);
CREATE INDEX idx_fact_txn_date ON fact_transactions (date_key);
CREATE INDEX idx_fact_txn_type ON fact_transactions (transaction_type);
CREATE INDEX idx_fact_perf_fund ON fact_performance (fund_key);
CREATE INDEX idx_fact_aum_fund ON fact_aum (fund_key);
