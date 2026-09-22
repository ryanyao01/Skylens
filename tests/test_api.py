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


@pytest.fixture
def client(flight_counts, weather, peak_observations):
    with (
        patch.object(main, "fetch_all_airport_counts", return_value=flight_counts),
        patch.object(main, "fetch_all_weather", return_value=weather),
        patch.object(main, "update_peak_observations", return_value=peak_observations),
        TestClient(main.app) as c,
    ):
        for _ in range(50):                     # wait for the scheduler's first pass
            if main.score_cache:
                break
            time.sleep(0.1)
        yield c


def test_health_reports_ok_once_scores_are_cached(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["airports_cached"] == 58
    assert body["last_refresh_error"] is None


def test_scores_endpoint_returns_every_airport(client):
    body = client.get("/airports/scores").json()
    assert len(body) == 58


def test_coordinates_are_merged_in_for_the_globe(client):
    """lat/lon/name come from the API layer, not the scorer."""
    body = client.get("/airports/scores").json()
    for code, airport in body.items():
        assert set(airport) >= CLIENT_FIELDS, f"{code} would break the map"
        assert -90 <= airport["lat"] <= 90
        assert -180 <= airport["lon"] <= 180
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
