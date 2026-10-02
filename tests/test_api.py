"""HTTP surface. Upstream calls are stubbed so tests never hit the network."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import skylens.api.main as main

# Fields the mobile client's AirportInfo interface depends on. Breaking any of
# these silently renders markers at the wrong place, colour, or not at all.
CLIENT_FIELDS = {"score", "lat", "lon", "name", "live_flights", "live_data_status"}


def _wait_for(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def client(models, flight_counts, weather, peak_observations, monkeypatch):
    # Module-level state survives between tests; start every test from scratch.
    for name, value in (("score_cache", {}), ("cascade_cache", {}), ("last_refresh_at", None),
                        ("last_refresh_error", None), ("last_quality", None)):
        monkeypatch.setattr(main, name, value)

    with (
        # Unpickling the three XGBoost models takes ~2 s; reuse the session's copy.
        patch.object(main, "load_models", return_value=models),
        patch.object(main, "fetch_all_airport_counts", return_value=flight_counts),
        patch.object(main, "fetch_all_weather", return_value=weather),
        patch.object(main, "update_peak_observations", return_value=peak_observations),
        TestClient(main.app) as c,
    ):
        assert _wait_for(lambda: main.last_quality is not None), "first refresh never finished"
        yield c


# ----------------------------------------------------------------------- live
def test_health_reports_ok_once_scores_are_cached(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["airports_cached"] == 58
    assert body["last_refresh_error"] is None
    assert body["data_quality"]["status"] in {"pass", "warn"}
    assert body["warehouse"] == {"enabled": True, "available": True, "runs_recorded": 1}


def test_scores_endpoint_returns_every_airport(client):
    assert len(client.get("/airports/scores").json()) == 58


def test_coordinates_are_merged_in_for_the_globe(client):
    """lat/lon/name come from the API layer, not the scorer."""
    for code, airport in client.get("/airports/scores").json().items():
        assert set(airport) >= CLIENT_FIELDS, f"{code} would break the map"
        assert -90 <= airport["lat"] <= 90 and -180 <= airport["lon"] <= 180
        assert airport["name"]


def test_single_airport_lookup_is_case_insensitive(client):
    assert client.get("/airports/atl/score").json() == client.get("/airports/ATL/score").json()


def test_unknown_airport_returns_404(client):
    assert client.get("/airports/zzz/score").status_code == 404


def test_cascade_endpoints(client):
    assert client.get("/forecast/cascade").status_code in (200, 503)
    assert client.get("/forecast/cascade/zzz").status_code == 404


def test_cors_headers_are_present_for_the_mobile_client(client):
    r = client.get("/airports/scores", headers={"Origin": "http://localhost:8081"})
    assert r.headers.get("access-control-allow-origin") == "*"


def test_openapi_schema_is_served(client):
    assert client.get("/openapi.json").status_code == 200


def test_upstream_failure_keeps_serving_the_last_good_scores(client, flight_counts):
    """A failed upstream request scores every airport 0.

    Serving that would paint the whole map as quiet. The API must keep the last
    good scores, say so in /health, and still record the failed run.
    """
    good = client.get("/airports/scores").json()
    failed = {**flight_counts, "_run": {**flight_counts["_run"], "status": "rate_limited"}}
    failed.update(dict.fromkeys(good, 0))
    with patch.object(main, "fetch_all_airport_counts", return_value=failed):
        main.refresh_scores()

    assert client.get("/airports/scores").json() == good
    health = client.get("/health").json()
    assert health["status"] == "degraded"
    assert "rate_limited" in health["last_refresh_error"]
    assert health["data_quality"]["status"] == "fail"
    assert health["warehouse"]["runs_recorded"] == 2


# ------------------------------------------------------------------ dashboard
def test_dashboard_is_served_at_the_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "SkyLens" in r.text and "leaflet" in r.text.lower()


# ------------------------------------------------------ pipeline & analytics
def test_quality_endpoint_lists_every_check(client):
    body = client.get("/quality").json()
    assert len(body["checks"]) == 10
    assert body["latest"]["run_id"]


def test_pipeline_runs_are_recorded(client):
    runs = client.get("/pipeline/runs").json()
    assert len(runs) == 1
    assert runs[0]["opensky_status"] == "ok"
    assert client.get("/pipeline/daily").json()[0]["runs"] == 1


def test_analytics_endpoints(client):
    assert len(client.get("/analytics/leaderboard?limit=5").json()) == 5
    hourly = client.get("/analytics/hourly/atl").json()
    assert len(hourly) == 1 and hourly[0]["airport"] == "ATL"
    history = client.get("/analytics/history/ATL?hours=24").json()
    assert len(history) == 1
    assert client.get("/analytics/history/ZZZ").status_code == 404


def test_backtest_withholds_a_verdict_without_enough_data(client):
    body = client.get("/analytics/cascade-backtest").json()
    assert body["verdict"] == "insufficient_data"
    assert body["matured_predictions"] == 0


def test_analytics_return_503_when_the_warehouse_is_disabled(client, monkeypatch):
    monkeypatch.setattr(main, "get_warehouse", lambda: None)
    assert client.get("/quality").status_code == 503
    assert client.get("/analytics/leaderboard").status_code == 503
