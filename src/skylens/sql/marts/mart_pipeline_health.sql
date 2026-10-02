-- Daily operational view of the ingestion job: is it running, and is it healthy?
CREATE OR REPLACE VIEW mart_pipeline_health AS
SELECT
    CAST(started_at AS DATE)                                     AS day_utc,
    count(*)                                                     AS runs,
    count(*) FILTER (WHERE opensky_status = 'ok')                AS successful_runs,
    round(100.0 * count(*) FILTER (WHERE opensky_status = 'ok') / count(*), 1)
                                                                 AS success_rate_pct,
    round(avg(duration_s), 2)                                    AS avg_duration_s,
    min(credits_remaining)                                       AS min_credits_remaining,
    round(avg(airports_degraded), 1)                             AS avg_airports_degraded,
    sum(cascade_triggers)                                        AS cascade_triggers
FROM ingestion_runs
GROUP BY CAST(started_at AS DATE);
