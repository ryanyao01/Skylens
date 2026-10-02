"""DuckDB warehouse: persistence, the SQL models, and the cascade backtest."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from skylens.airports import AIRPORTS
from skylens.warehouse import Warehouse


@pytest.fixture
def wh(tmp_path):
    w = Warehouse(tmp_path / "test.duckdb", trained_airports={"ATL", "ORD"})
    yield w
    w.close()


@pytest.fixture
def scored(models, flight_counts, weather, peak_observations):
    from skylens.pipeline.scorer import compute_scores

    return compute_scores(models, flight_counts, weather, peak_observations)


def _record(wh, flight_counts, weather, scores, run_id="r1", started=None, cascade=None):
    started = started or datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
    wh.record_run(
        run_id=run_id, started_at=started, finished_at=started + timedelta(seconds=5),
        flight_counts=flight_counts, weather=weather, scores=scores, cascade=cascade or {},
    )


# --------------------------------------------------------------- persistence
def test_dimension_table_is_seeded(wh):
    assert wh.scalar("SELECT count(*) FROM dim_airports") == len(AIRPORTS)
    assert wh.scalar("SELECT count(*) FROM dim_airports WHERE has_model") == 2


def test_a_run_lands_in_every_table(wh, flight_counts, weather, scored):
    cascade = {"ATL": {1: {"ORD": 12.5}, 2: {}}}
    _record(wh, flight_counts, weather, scored, cascade=cascade)
    assert wh.scalar("SELECT count(*) FROM ingestion_runs") == 1
    assert wh.scalar("SELECT count(*) FROM raw_observations") == len(AIRPORTS)
    assert wh.scalar("SELECT count(*) FROM fact_airport_scores") == len(AIRPORTS)
    assert wh.scalar("SELECT count(*) FROM fact_cascade_predictions") == 1
    run = wh.query("SELECT * FROM ingestion_runs")[0]
    assert run["opensky_status"] == "ok" and run["credits_remaining"] == 3_900


def test_local_hour_is_stored_on_the_airport_clock(wh, flight_counts, weather, scored):
    _record(wh, flight_counts, weather, scored)
    rows = {r["airport"]: r for r in wh.query("SELECT airport, local_hour FROM fact_airport_scores")}
    expected = AIRPORTS["ATL"].local_time(datetime.fromisoformat(scored["ATL"]["timestamp"])).hour
    assert rows["ATL"]["local_hour"] == expected


def test_a_run_is_all_or_nothing(wh, flight_counts, weather, scored):
    """A bad row midway must not leave a run half-written."""
    scored["ATL"]["score"] = "not a number"
    with pytest.raises(Exception):  # noqa: B017 - any DuckDB conversion error
        _record(wh, flight_counts, weather, scored)
    assert wh.scalar("SELECT count(*) FROM ingestion_runs") == 0
    assert wh.scalar("SELECT count(*) FROM raw_observations") == 0


def test_previous_run_total_reads_the_latest_good_run(wh, flight_counts, weather, scored):
    assert wh.previous_run_aircraft_total() is None
    _record(wh, flight_counts, weather, scored)
    assert wh.previous_run_aircraft_total() == 30 * len(AIRPORTS)


# ------------------------------------------------------------------ staging
def test_staging_excludes_failed_runs_and_missing_data(wh, flight_counts, weather, scored):
    flight_counts["_metadata"]["PVG"]["status"] = "no_states"
    scored["PVG"]["live_data_status"] = "no_states"
    _record(wh, flight_counts, weather, scored, run_id="good")

    failed = {**flight_counts, "_run": {**flight_counts["_run"], "status": "rate_limited"}}
    _record(wh, failed, weather, scored, run_id="bad",
            started=datetime(2026, 10, 2, 12, 15, tzinfo=UTC))

    assert wh.scalar("SELECT count(*) FROM fact_airport_scores") == 2 * len(AIRPORTS)
    assert wh.scalar("SELECT count(DISTINCT run_id) FROM stg_scores") == 1
    assert wh.scalar("SELECT count(*) FROM stg_scores WHERE airport = 'PVG'") == 0


def test_marts_aggregate_history(wh, flight_counts, weather, scored):
    _record(wh, flight_counts, weather, scored)
    board = wh.query("SELECT * FROM mart_airport_leaderboard")
    assert len(board) == len(AIRPORTS)
    assert wh.query("SELECT * FROM mart_pipeline_health")[0]["runs"] == 1
    assert wh.scalar("SELECT count(*) FROM mart_airport_hourly") == len(AIRPORTS)


# ----------------------------------------------------------------- backtest
def _seed_backtest(wh, *, named_rise: float, control_rise: float, runs: int = 6):
    """A synthetic world where the right answer is known.

    Each run, trigger T fires and names N as impacted at horizon 1. One hour
    later N's score has moved by `named_rise`; controls C1..C3 by `control_rise`.
    """
    cur = wh._con.cursor()
    t0 = datetime(2026, 10, 1, 0, 0)
    for i in range(runs):
        at = t0 + timedelta(hours=2 * i)
        later = at + timedelta(hours=1, minutes=5)          # within the 30-min tolerance
        for run_id, ts in ((f"p{i}", at), (f"o{i}", later)):
            cur.execute("INSERT INTO ingestion_runs (run_id, started_at, finished_at, opensky_status)"
                        " VALUES (?, ?, ?, 'ok')", [run_id, ts, ts])
        base = 40 + i  # vary so the variance is non-zero
        for code, before, after in (
            ("T", 80, 80), ("N", base, base + named_rise),
            ("C1", base, base + control_rise), ("C2", base + 1, base + 1 + control_rise * 1.1),
            ("C3", base + 2, base + 2 + control_rise * 0.9),
        ):
            for run_id, ts, score in ((f"p{i}", at, before), (f"o{i}", later, after)):
                cur.execute("INSERT INTO fact_airport_scores (run_id, observed_at, airport, score, data_status)"
                            " VALUES (?, ?, ?, ?, 'ok')", [run_id, ts, code, score])
        cur.execute("INSERT INTO fact_cascade_predictions VALUES (?, ?, 'T', 80, 1, 'N', 20)", [f"p{i}", at])


def test_backtest_detects_a_real_propagation_effect(wh):
    _seed_backtest(wh, named_rise=20, control_rise=1)
    h1 = wh.query("SELECT * FROM mart_cascade_backtest WHERE horizon_h = 1")[0]
    assert h1["n_predicted"] == 6
    assert h1["n_control"] == 18
    assert h1["lift"] == pytest.approx(19, abs=0.5)
    assert h1["welch_t"] > 2


def test_backtest_finds_nothing_when_there_is_nothing(wh):
    _seed_backtest(wh, named_rise=1, control_rise=1)
    h1 = wh.query("SELECT * FROM mart_cascade_backtest WHERE horizon_h = 1")[0]
    assert abs(h1["lift"]) < 0.5


def test_backtest_excludes_triggers_and_unmatured_predictions(wh):
    _seed_backtest(wh, named_rise=20, control_rise=1, runs=6)
    outcomes = wh.query("SELECT DISTINCT airport FROM int_cascade_outcomes")
    assert "T" not in {r["airport"] for r in outcomes}, "the trigger is neither named nor control"
    # The last prediction (run p5) is followed by one observation an hour later,
    # so only its 1-hour horizon can mature; 2-6 h targets lie in the future.
    matured = wh.query(
        "SELECT DISTINCT horizon_h FROM int_cascade_outcomes WHERE run_id = 'p5' ORDER BY 1"
    )
    assert [r["horizon_h"] for r in matured] == [1]


def test_an_outcome_too_far_from_its_target_time_is_not_used(wh):
    cur = wh._con.cursor()
    at = datetime(2026, 10, 1, 0, 0)
    far = at + timedelta(hours=1, minutes=45)  # 45 min past target: a different moment
    for run_id, ts in (("p", at), ("o", far)):
        cur.execute("INSERT INTO ingestion_runs (run_id, started_at, finished_at, opensky_status)"
                    " VALUES (?, ?, ?, 'ok')", [run_id, ts, ts])
        for code in ("T", "N", "C"):
            cur.execute("INSERT INTO fact_airport_scores (run_id, observed_at, airport, score, data_status)"
                        " VALUES (?, ?, ?, 50, 'ok')", [run_id, ts, code])
    cur.execute("INSERT INTO fact_cascade_predictions VALUES ('p', ?, 'T', 80, 1, 'N', 20)", [at])
    assert wh.scalar("SELECT count(*) FROM int_cascade_outcomes") == 0


def test_hostile_text_is_stored_as_data(wh):
    """Bulk inserts go through a JSON parameter; text must never become SQL."""
    nasty = "it's \"quoted\" -- '); DROP TABLE dq_results; --"
    wh.record_quality("r1", datetime(2026, 10, 2, tzinfo=UTC), [{
        "check_name": "probe", "severity": "warning", "passed": True,
        "observed": nasty, "expectation": nasty,
    }])
    assert wh.scalar("SELECT observed FROM dq_results") == nasty


def test_nan_is_stored_as_null_not_rejected(wh, flight_counts, weather, scored):
    """NaN is not valid JSON. It becomes NULL; the score_in_range check flags it."""
    scored["ATL"]["projected_score"] = float("nan")
    _record(wh, flight_counts, weather, scored)
    assert wh.scalar("SELECT projected_score FROM fact_airport_scores WHERE airport = 'ATL'") is None
