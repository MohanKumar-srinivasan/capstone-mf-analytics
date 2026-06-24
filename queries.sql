-- ============================================================
-- Bluestock Mutual Fund Analytics — Analytical Queries
-- Day 2 Deliverable: 10 analytical SQL queries
-- Run against: bluestock_mf.db
-- ============================================================

-- --------------------------------------------------------------
-- 1. Top 5 funds by latest AUM
-- --------------------------------------------------------------
SELECT f.scheme_name, f.fund_house, a.aum_cr, d.full_date
FROM fact_aum a
JOIN dim_fund f ON f.fund_key = a.fund_key
JOIN dim_date d ON d.date_key = a.date_key
WHERE a.date_key = (SELECT MAX(date_key) FROM fact_aum)
ORDER BY a.aum_cr DESC
LIMIT 5;


-- --------------------------------------------------------------
-- 2. Average NAV per month, per fund
-- --------------------------------------------------------------
SELECT f.scheme_name, d.year, d.month, ROUND(AVG(n.nav), 2) AS avg_nav
FROM fact_nav n
JOIN dim_fund f ON f.fund_key = n.fund_key
JOIN dim_date d ON d.date_key = n.date_key
GROUP BY f.scheme_name, d.year, d.month
ORDER BY f.scheme_name, d.year, d.month;


-- --------------------------------------------------------------
-- 3. SIP Year-over-Year (YoY) growth in total SIP amount
-- --------------------------------------------------------------
WITH sip_yearly AS (
    SELECT d.year, SUM(t.amount) AS total_sip
    FROM fact_transactions t
    JOIN dim_date d ON d.date_key = t.date_key
    WHERE t.transaction_type = 'SIP'
    GROUP BY d.year
)
SELECT year,
       total_sip,
       LAG(total_sip) OVER (ORDER BY year) AS prev_year_sip,
       ROUND(
         100.0 * (total_sip - LAG(total_sip) OVER (ORDER BY year))
         / LAG(total_sip) OVER (ORDER BY year), 2
       ) AS yoy_growth_pct
FROM sip_yearly
ORDER BY year;


-- --------------------------------------------------------------
-- 4. Transactions by state
-- --------------------------------------------------------------
SELECT state,
       COUNT(*) AS num_transactions,
       ROUND(SUM(amount), 2) AS total_amount,
       ROUND(AVG(amount), 2) AS avg_amount
FROM fact_transactions
GROUP BY state
ORDER BY total_amount DESC;


-- --------------------------------------------------------------
-- 5. Funds with expense_ratio < 1%  (latest performance record per fund)
-- --------------------------------------------------------------
WITH latest_perf AS (
    SELECT fund_key, MAX(date_key) AS max_date_key
    FROM fact_performance
    GROUP BY fund_key
)
SELECT f.scheme_name, f.fund_house, p.expense_ratio_pct, d.full_date
FROM fact_performance p
JOIN latest_perf lp ON lp.fund_key = p.fund_key AND lp.max_date_key = p.date_key
JOIN dim_fund f ON f.fund_key = p.fund_key
JOIN dim_date d ON d.date_key = p.date_key
WHERE p.expense_ratio_pct < 1.0
ORDER BY p.expense_ratio_pct ASC;


-- --------------------------------------------------------------
-- 6. Top 5 funds by 3-year return (latest performance snapshot)
-- --------------------------------------------------------------
WITH latest_perf AS (
    SELECT fund_key, MAX(date_key) AS max_date_key
    FROM fact_performance
    GROUP BY fund_key
)
SELECT f.scheme_name, f.category, p.returns_3y_pct
FROM fact_performance p
JOIN latest_perf lp ON lp.fund_key = p.fund_key AND lp.max_date_key = p.date_key
JOIN dim_fund f ON f.fund_key = p.fund_key
ORDER BY p.returns_3y_pct DESC
LIMIT 5;


-- --------------------------------------------------------------
-- 7. Investor transaction mix (% split of SIP / Lumpsum / Redemption by count and value)
-- --------------------------------------------------------------
SELECT transaction_type,
       COUNT(*) AS num_txns,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM fact_transactions), 2) AS pct_of_txns,
       ROUND(SUM(amount), 2) AS total_value,
       ROUND(100.0 * SUM(amount) / (SELECT SUM(amount) FROM fact_transactions), 2) AS pct_of_value
FROM fact_transactions
GROUP BY transaction_type
ORDER BY total_value DESC;


-- --------------------------------------------------------------
-- 8. KYC status breakdown by state (compliance check)
-- --------------------------------------------------------------
SELECT state, kyc_status, COUNT(*) AS num_investors_txns
FROM fact_transactions
GROUP BY state, kyc_status
ORDER BY state, kyc_status;


-- --------------------------------------------------------------
-- 9. Fund category performance comparison (avg 1y return & avg expense ratio by category)
-- --------------------------------------------------------------
SELECT f.category,
       ROUND(AVG(p.returns_1y_pct), 2) AS avg_1y_return,
       ROUND(AVG(p.expense_ratio_pct), 2) AS avg_expense_ratio,
       COUNT(DISTINCT f.fund_key) AS num_funds
FROM fact_performance p
JOIN dim_fund f ON f.fund_key = p.fund_key
GROUP BY f.category
ORDER BY avg_1y_return DESC;


-- --------------------------------------------------------------
-- 10. NAV growth: first vs latest NAV per fund (cumulative return proxy)
-- --------------------------------------------------------------
WITH first_nav AS (
    SELECT fund_key, nav AS start_nav,
           ROW_NUMBER() OVER (PARTITION BY fund_key ORDER BY date_key ASC) AS rn
    FROM fact_nav
),
last_nav AS (
    SELECT fund_key, nav AS end_nav,
           ROW_NUMBER() OVER (PARTITION BY fund_key ORDER BY date_key DESC) AS rn
    FROM fact_nav
)
SELECT f.scheme_name,
       fn.start_nav,
       ln.end_nav,
       ROUND(100.0 * (ln.end_nav - fn.start_nav) / fn.start_nav, 2) AS pct_growth_over_period
FROM first_nav fn
JOIN last_nav ln ON ln.fund_key = fn.fund_key AND ln.rn = 1
JOIN dim_fund f ON f.fund_key = fn.fund_key
WHERE fn.rn = 1
ORDER BY pct_growth_over_period DESC;
