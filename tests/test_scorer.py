"""Scoring pipeline: helpers, the score formula, and the model-driven forecast."""

from __future__ import annotations

import pytest

from skylens.pipeline.opensky import extract_count
from skylens.pipeline.scorer import _next_hour_slot, _trend, compute_scores

REQUIRED_FIELDS = {
    "score", "projected_score", "expected_arrivals", "forecast_next_hour",
    "demand_trend", "forecast_source", "live_flights", "pred_capacity",
    "hist_mean_arrivals", "offline_peak_capacity", "live_peak_count",
    "peak_source", "weather_penalty", "wind_kn", "precip_mm", "visibility_m",
    "model_trained", "scoring_basis", "live_data_status", "live_data_message",
    "timestamp",
}


@pytest.mark.parametrize(
    ("value", "expected"),
    [({"count": 7}, 7), ({"count": 0}, 0), ({"count": None}, 0), ({}, 0), (12, 12), (0, 0), (None, 0)],
)
def test_extract_count_handles_both_payload_shapes(value, expected):
    """Counts arrive as a bare int from older callers and a dict from the API."""
    assert extract_count(value) == expected


@pytest.mark.parametrize(
    ("dow", "hour", "expected"),
    [(3, 10, (3, 11)), (3, 22, (3, 23)), (3, 23, (4, 0)), (7, 23, (1, 0))],
)
def test_next_hour_slot_rolls_over_midnight_and_week(dow, hour, expected):
    assert _next_hour_slot(dow, hour) == expected


@pytest.mark.parametrize(
    ("now", "later", "expected"),
    [(1.0, 1.2, "rising"), (1.0, 0.8, "falling"), (1.0, 1.05, "steady"),
     (1.0, 1.0, "steady"), (0.0, 5.0, "unknown")],
)
def test_trend_classification(now, later, expected):
    assert _trend(now, later) == expected


def test_every_airport_is_scored_with_the_full_field_set(models, flight_counts, weather, peak_observations):
    scores = compute_scores(models, flight_counts, weather, peak_observations)
    assert len(scores) == 58
    for code, data in scores.items():
        assert set(data) >= REQUIRED_FIELDS, f"{code} missing {REQUIRED_FIELDS - set(data)}"


def test_scores_stay_within_bounds(models, flight_counts, weather, peak_observations):
    scores = compute_scores(models, flight_counts, weather, peak_observations)
    for code, d in scores.items():
        assert 0.0 <= d["score"] <= 100.0, code
        assert 0.0 <= d["projected_score"] <= 100.0, code


def test_score_scales_with_live_traffic(models, flight_counts, weather, peak_observations):
    """Doubling aircraft should double the score while below the cap."""
    low = compute_scores(models, {**flight_counts, "ATL": {"count": 10, "status": "ok"}},
                         weather, peak_observations)["ATL"]["score"]
    high = compute_scores(models, {**flight_counts, "ATL": {"count": 20, "status": "ok"}},
                          weather, peak_observations)["ATL"]["score"]
    assert high == pytest.approx(low * 2, rel=0.02)


def test_score_is_capped_at_100(models, flight_counts, weather, peak_observations):
    counts = {**flight_counts, "ATL": {"count": 99999, "status": "ok"}}
    assert compute_scores(models, counts, weather, peak_observations)["ATL"]["score"] == 100.0


def test_bad_weather_raises_the_score(models, flight_counts, weather, peak_observations):
    """Worse weather shrinks effective capacity, so the same traffic scores higher."""
    storm = {**weather, "ATL": {"wind_speed_kn": 40, "wind_gusts_kn": 50,
                                "precipitation_mm": 10, "visibility_m": 1000}}
    calm = compute_scores(models, flight_counts, weather, peak_observations)["ATL"]["score"]
    rough = compute_scores(models, flight_counts, storm, peak_observations)["ATL"]["score"]
    assert rough > calm


def test_trained_airports_forecast_from_the_model(models, flight_counts, weather, peak_observations):
    """The q10/q50/q90 models must actually reach the output."""
    scores = compute_scores(models, flight_counts, weather, peak_observations)
    modelled = [d for d in scores.values() if d["forecast_source"] == "model"]
    assert len(modelled) == 43
    for d in modelled:
        f = d["forecast_next_hour"]
        assert f["p10"] is not None and f["p90"] is not None
        assert f["p10"] <= f["p50"] <= f["p90"], "quantiles must be ordered"


def test_untrained_airports_fall_back_to_history(models, flight_counts, weather, peak_observations):
    scores = compute_scores(models, flight_counts, weather, peak_observations)
    historical = [d for d in scores.values() if d["forecast_source"] == "historical"]
    assert len(historical) == 15
    for d in historical:
        assert d["forecast_next_hour"]["p10"] is None, "no uncertainty band without a model"
        assert d["demand_trend"] in {"rising", "falling", "steady", "unknown"}


def test_observed_peak_overrides_the_calibrated_baseline(models, flight_counts, weather):
    """A live observation above the profile baseline must take precedence."""
    huge = {code: {"peak": 9999, "observations": 10} for code in flight_counts if not code.startswith("_")}
    d = compute_scores(models, flight_counts, weather, huge)["ATL"]
    assert d["peak_source"] == "observed"
    assert d["live_peak_count"] == 9999


def test_degraded_airports_are_still_scored_and_flagged(models, flight_counts, weather, peak_observations):
    counts = {**flight_counts, "PVG": {"count": 0, "status": "no_states"}}
    counts["_metadata"] = {**counts["_metadata"],
                           "PVG": {"status": "no_states", "message": "no coverage"}}
    d = compute_scores(models, counts, weather, peak_observations)["PVG"]
    assert d["live_data_status"] == "no_states"
    assert d["score"] == 0.0
