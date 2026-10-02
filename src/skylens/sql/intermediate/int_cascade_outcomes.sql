-- One row per (run, horizon, airport) for every run in which the cascade fired:
-- the airport's score when the prediction was made, and its score `horizon_h`
-- hours later.
--
-- Cohorts:
--   predicted  airports the cascade named for this horizon
--   control    airports it did not name at any horizon, and that were not
--              themselves triggers -- the null model in which nothing spreads
--
-- Comparing the two cohorts over the *same* time windows cancels out effects
-- that move every airport at once, like the morning ramp-up.
--
-- Outcomes are matched with an ASOF join: the first observation at or after
-- the target time, accepted only if it lands within 30 minutes of it.
-- Predictions whose target time has not arrived yet simply do not appear.
CREATE OR REPLACE VIEW int_cascade_outcomes AS
WITH fired AS (
    SELECT DISTINCT run_id, predicted_at
    FROM stg_cascade_predictions
),
horizons AS (
    SELECT f.run_id, f.predicted_at, h.horizon_h
    FROM fired AS f
    CROSS JOIN range(1, 7) AS h(horizon_h)
),
named AS (
    SELECT run_id, horizon_h, impacted_airport AS airport, max(predicted_impact) AS predicted_impact
    FROM stg_cascade_predictions
    GROUP BY run_id, horizon_h, impacted_airport
),
named_any_horizon AS (
    SELECT DISTINCT run_id, impacted_airport AS airport
    FROM stg_cascade_predictions
),
triggers AS (
    SELECT DISTINCT run_id, trigger_airport AS airport
    FROM stg_cascade_predictions
),
labelled AS (
    SELECT
        h.run_id,
        h.predicted_at,
        h.horizon_h,
        s.airport,
        s.score AS score_at_prediction,
        CASE WHEN n.airport IS NOT NULL THEN 'predicted' ELSE 'control' END AS cohort,
        n.predicted_impact,
        h.predicted_at + to_hours(CAST(h.horizon_h AS BIGINT)) AS target_at
    FROM horizons AS h
    JOIN stg_scores AS s
        ON s.run_id = h.run_id
    LEFT JOIN named AS n
        ON n.run_id = h.run_id AND n.horizon_h = h.horizon_h AND n.airport = s.airport
    WHERE NOT EXISTS (
            SELECT 1 FROM triggers AS t
            WHERE t.run_id = h.run_id AND t.airport = s.airport
        )
      -- named at some other horizon: neither this horizon's prediction nor a
      -- clean control, so leave it out
      AND (
            n.airport IS NOT NULL
            OR NOT EXISTS (
                SELECT 1 FROM named_any_horizon AS a
                WHERE a.run_id = h.run_id AND a.airport = s.airport
            )
        )
)
SELECT
    l.run_id,
    l.predicted_at,
    l.horizon_h,
    l.airport,
    l.cohort,
    l.predicted_impact,
    l.target_at,
    l.score_at_prediction,
    o.observed_at AS outcome_at,
    o.score AS score_at_outcome,
    o.score - l.score_at_prediction AS score_delta
FROM labelled AS l
ASOF JOIN stg_scores AS o
    ON o.airport = l.airport
   AND o.observed_at >= l.target_at
WHERE o.observed_at <= l.target_at + INTERVAL 30 MINUTE;
