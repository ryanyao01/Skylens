-- Trustworthy score observations only. Everything downstream builds on this.
--
-- Excludes:
--   * runs where the upstream OpenSky request failed -- every airport reads 0
--     then, which is missing data, not empty skies
--   * airports flagged no_states, where 0 aircraft may mean a receiver
--     coverage gap rather than a quiet airport
CREATE OR REPLACE VIEW stg_scores AS
SELECT
    s.run_id,
    s.observed_at,
    s.airport,
    s.local_hour,
    s.local_dow,
    s.score,
    s.projected_score,
    s.live_flights,
    s.live_peak_count,
    s.weather_penalty,
    s.expected_arrivals,
    s.forecast_p10,
    s.forecast_p50,
    s.forecast_p90,
    s.demand_trend,
    s.forecast_source,
    s.model_trained
FROM fact_airport_scores AS s
JOIN ingestion_runs AS r USING (run_id)
WHERE r.opensky_status = 'ok'
  AND s.data_status = 'ok'
  AND s.score IS NOT NULL;
