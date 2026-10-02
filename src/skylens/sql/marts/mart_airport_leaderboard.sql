-- Which airports are under the most sustained pressure?
-- pct_time_stressed uses the cascade's own threshold of 65.
CREATE OR REPLACE VIEW mart_airport_leaderboard AS
SELECT
    s.airport,
    d.name,
    count(*)                                            AS observations,
    round(avg(s.score), 1)                              AS avg_score,
    round(100 * avg(CAST(s.score >= 65 AS INTEGER)), 1) AS pct_time_stressed,
    max(s.score)                                        AS max_score,
    arg_max(s.local_hour, s.score)                      AS local_hour_of_max,
    max(s.observed_at)                                  AS last_observed_at
FROM stg_scores AS s
JOIN dim_airports AS d ON d.code = s.airport
GROUP BY s.airport, d.name;
