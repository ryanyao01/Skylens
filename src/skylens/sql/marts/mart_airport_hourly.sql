-- Typical congestion by airport and LOCAL hour of day.
-- Answers: when does each airport run hot?
CREATE OR REPLACE VIEW mart_airport_hourly AS
SELECT
    airport,
    local_hour,
    count(*)                             AS observations,
    round(avg(score), 1)                 AS avg_score,
    round(quantile_cont(score, 0.9), 1)  AS p90_score,
    round(avg(live_flights), 1)          AS avg_aircraft
FROM stg_scores
GROUP BY airport, local_hour;
