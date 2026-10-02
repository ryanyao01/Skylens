-- Does the cascade model predict anything?
--
-- For each horizon, compare how the scores of airports the cascade named
-- changed against airports it did not name, over the same windows.
--
--   lift      mean score change (predicted) - mean score change (control).
--             Positive means named airports got relatively busier, as predicted.
--   welch_t   Welch two-sample t statistic for that difference. |t| above
--             about 2 suggests it is unlikely to be noise.
--
-- Known weakness of this design: named airports are graph neighbours of busy
-- hubs, so they are not a random sample. A stronger null would compare each
-- airport against its own typical change at the same local hour.
CREATE OR REPLACE VIEW mart_cascade_backtest AS
WITH stats AS (
    SELECT
        horizon_h,
        count(*) FILTER (WHERE cohort = 'predicted')                        AS n_predicted,
        count(*) FILTER (WHERE cohort = 'control')                          AS n_control,
        avg(score_delta) FILTER (WHERE cohort = 'predicted')                AS mean_predicted,
        avg(score_delta) FILTER (WHERE cohort = 'control')                  AS mean_control,
        var_samp(score_delta) FILTER (WHERE cohort = 'predicted')           AS var_predicted,
        var_samp(score_delta) FILTER (WHERE cohort = 'control')             AS var_control,
        avg(CAST(score_delta > 0 AS INTEGER)) FILTER (WHERE cohort = 'predicted') AS rose_predicted,
        avg(CAST(score_delta > 0 AS INTEGER)) FILTER (WHERE cohort = 'control')   AS rose_control
    FROM int_cascade_outcomes
    GROUP BY horizon_h
)
SELECT
    horizon_h,
    n_predicted,
    n_control,
    round(mean_predicted, 2)                 AS mean_delta_predicted,
    round(mean_control, 2)                   AS mean_delta_control,
    round(mean_predicted - mean_control, 2)  AS lift,
    round(100 * rose_predicted, 1)           AS pct_predicted_rose,
    round(100 * rose_control, 1)             AS pct_control_rose,
    CASE
        WHEN n_predicted >= 2 AND n_control >= 2
             AND var_predicted / n_predicted + var_control / n_control > 0
        THEN round(
            (mean_predicted - mean_control)
            / sqrt(var_predicted / n_predicted + var_control / n_control),
            2)
    END AS welch_t
FROM stats
ORDER BY horizon_h;
