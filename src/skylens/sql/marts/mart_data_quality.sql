-- Every data-quality check: its latest result and its pass rate over all runs.
CREATE OR REPLACE VIEW mart_data_quality AS
SELECT
    check_name,
    arg_max(severity, checked_at)     AS severity,
    arg_max(passed, checked_at)       AS latest_passed,
    arg_max(observed, checked_at)     AS latest_observed,
    arg_max(expectation, checked_at)  AS expectation,
    max(checked_at)                   AS last_checked_at,
    count(*)                          AS runs_checked,
    round(100 * avg(CAST(passed AS INTEGER)), 1) AS pass_rate_pct
FROM dq_results
GROUP BY check_name;
