-- Cascade predictions from runs whose upstream data was good. A prediction made
-- from a failed run was made from zeros and says nothing about the model.
CREATE OR REPLACE VIEW stg_cascade_predictions AS
SELECT
    p.run_id,
    p.predicted_at,
    p.trigger_airport,
    p.trigger_score,
    p.horizon_h,
    p.impacted_airport,
    p.predicted_impact
FROM fact_cascade_predictions AS p
JOIN ingestion_runs AS r USING (run_id)
WHERE r.opensky_status = 'ok';
