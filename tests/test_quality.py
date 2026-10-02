"""Data-quality checks: each one must pass on good data and catch its failure."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from skylens import quality


@pytest.fixture
def good_scores(models, flight_counts, weather, peak_observations):
    from skylens.pipeline.scorer import compute_scores

    return compute_scores(models, flight_counts, weather, peak_observations)


def _check(results, name):
    return next(r for r in results if r["check_name"] == name)


def _run(flight_counts, weather, scores, previous=None, now=None):
    return quality.run_checks(
        flight_counts=flight_counts, weather=weather, scores=scores,
        now=now or datetime.now(UTC), previous_aircraft_total=previous,
    )


def test_every_check_passes_on_a_healthy_run(flight_counts, weather, good_scores):
    results = _run(flight_counts, weather, good_scores)
    failed = [r["check_name"] for r in results if not r["passed"]]
    assert not failed
    assert quality.summarize(results) == "pass"


def test_checks_are_unique_and_well_formed(flight_counts, weather, good_scores):
    results = _run(flight_counts, weather, good_scores)
    names = [r["check_name"] for r in results]
    assert len(names) == len(set(names)) == 10
    assert {r["severity"] for r in results} <= {quality.CRITICAL, quality.WARNING}


def test_a_failed_upstream_request_is_critical(flight_counts, weather, good_scores):
    flight_counts["_run"]["status"] = "rate_limited"
    results = _run(flight_counts, weather, good_scores)
    assert not _check(results, "opensky_request_ok")["passed"]
    assert quality.summarize(results) == "fail"


def test_stale_upstream_data_is_caught(flight_counts, weather, good_scores):
    old = time.time() - 3600
    for m in flight_counts["_metadata"].values():
        m["api_time"] = old
    assert not _check(_run(flight_counts, weather, good_scores), "opensky_data_fresh")["passed"]


def test_a_score_outside_0_100_is_critical(flight_counts, weather, good_scores):
    good_scores["ATL"]["score"] = 140.0
    results = _run(flight_counts, weather, good_scores)
    assert not _check(results, "score_in_range")["passed"]
    assert "ATL" in _check(results, "score_in_range")["observed"]
    assert quality.summarize(results) == "fail"


def test_a_missing_airport_is_critical(flight_counts, weather, good_scores):
    del good_scores["SEA"]
    assert not _check(_run(flight_counts, weather, good_scores), "all_airports_scored")["passed"]


def test_low_live_coverage_is_a_warning_not_a_failure(flight_counts, weather, good_scores):
    for code in list(flight_counts["_metadata"])[:10]:
        flight_counts["_metadata"][code]["status"] = "no_states"
    results = _run(flight_counts, weather, good_scores)
    assert not _check(results, "live_data_coverage")["passed"]
    assert quality.summarize(results) == "warn"


def test_missing_weather_is_flagged(flight_counts, weather, good_scores):
    for code in list(weather)[:20]:
        weather[code] = {}
    assert not _check(_run(flight_counts, weather, good_scores), "weather_coverage")["passed"]


def test_an_implausibly_empty_sky_is_flagged(flight_counts, weather, good_scores):
    """HTTP 200 with almost no aircraft is still a broken feed."""
    flight_counts["_run"]["aircraft_worldwide"] = 40
    assert not _check(_run(flight_counts, weather, good_scores), "aircraft_volume_plausible")["passed"]


def test_low_quota_is_flagged_before_it_runs_out(flight_counts, weather, good_scores):
    flight_counts["_run"]["credits_remaining"] = 120
    assert not _check(_run(flight_counts, weather, good_scores), "api_quota_headroom")["passed"]


def test_a_sudden_run_over_run_swing_is_flagged(flight_counts, weather, good_scores):
    current = 30 * 58
    assert not _check(_run(flight_counts, weather, good_scores, previous=current * 4),
                      "aircraft_volume_stable")["passed"]
    assert _check(_run(flight_counts, weather, good_scores, previous=current),
                  "aircraft_volume_stable")["passed"]


def test_disordered_quantiles_are_flagged(flight_counts, weather, good_scores):
    modelled = next(c for c, d in good_scores.items() if d["forecast_source"] == "model")
    good_scores[modelled]["forecast_next_hour"] = {"p10": 3.0, "p50": 2.0, "p90": 1.0}
    assert not _check(_run(flight_counts, weather, good_scores), "forecast_quantiles_ordered")["passed"]
