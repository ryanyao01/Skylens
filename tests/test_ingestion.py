"""Upstream ingestion: the single global OpenSky request and the weather batch.

All HTTP is mocked; these tests pin down behaviour under failure, which is
exactly the behaviour that is invisible when everything works.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from skylens.airports import AIRPORTS
from skylens.pipeline import opensky, weather


def _state(lon, lat):
    """A minimal OpenSky state vector: only indices 5 (lon) and 6 (lat) matter here."""
    return [None, None, None, None, None, lon, lat]


def _response(status=200, json=None, headers=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json if json is not None else {}
    r.headers = headers or {}
    return r


@pytest.fixture(autouse=True)
def no_auth_no_sleep():
    with (
        patch.object(opensky.tokens, "headers", return_value={}),
        patch.object(opensky.time, "sleep"),
    ):
        yield


# ------------------------------------------------------------ box filtering
def test_aircraft_are_counted_in_the_right_box():
    atl = AIRPORTS["ATL"]
    counts = opensky.count_aircraft_in_boxes([_state(atl.lon, atl.lat), _state(atl.lon, atl.lat)])
    assert counts["ATL"] == 2
    assert sum(counts.values()) == 2


def test_aircraft_without_a_position_are_skipped():
    assert sum(opensky.count_aircraft_in_boxes([_state(None, None), _state(-84.4, None)]).values()) == 0


def test_overlapping_boxes_both_count_an_aircraft():
    """JFK and LGA boxes overlap; separate bbox queries counted such aircraft twice."""
    lga = AIRPORTS["LGA"]
    counts = opensky.count_aircraft_in_boxes([_state(lga.lon, lga.lat)])
    assert counts["LGA"] == 1
    assert counts["JFK"] == 1


def test_aircraft_far_from_every_airport_count_nowhere():
    assert sum(opensky.count_aircraft_in_boxes([_state(-30.0, 0.0)]).values()) == 0  # mid-Atlantic


# ---------------------------------------------------------- global request
def test_success_returns_states_and_remaining_credits():
    with patch.object(opensky.requests, "get", return_value=_response(
        200, {"time": 1, "states": [_state(0, 0)]}, {"X-Rate-Limit-Remaining": "3996"}
    )) as get:
        states, info = opensky.fetch_global_states()
    assert len(states) == 1
    assert info["status"] == "ok" and info["credits_remaining"] == 3996
    assert get.call_count == 1


def test_quota_exhaustion_fails_fast_without_retrying():
    """Regression: the old per-airport loop exhausted the 4,000-credit daily quota.

    Once it is spent, retrying cannot succeed, so a 429 must not be hammered.
    """
    with patch.object(opensky.requests, "get", return_value=_response(
        429, headers={"X-Rate-Limit-Remaining": "0", "X-Rate-Limit-Retry-After-Seconds": "3600"}
    )) as get:
        states, info = opensky.fetch_global_states()
    assert states is None
    assert info["status"] == "rate_limited"
    assert "3600" in info["message"]
    assert get.call_count == 1


def test_server_errors_are_retried_then_succeed():
    responses = [_response(503), _response(200, {"time": 1, "states": []})]
    with patch.object(opensky.requests, "get", side_effect=responses) as get:
        states, info = opensky.fetch_global_states()
    assert states == []
    assert info["attempts"] == 2
    assert get.call_count == 2


def test_network_errors_give_up_after_max_attempts():
    with patch.object(opensky.requests, "get", side_effect=requests.ConnectionError("down")) as get:
        states, info = opensky.fetch_global_states()
    assert states is None
    assert info["status"] == "network_error"
    assert get.call_count == opensky.MAX_ATTEMPTS


def test_a_rejected_token_is_refreshed_and_retried():
    responses = [_response(401), _response(200, {"time": 1, "states": []})]
    with (
        patch.object(opensky.requests, "get", side_effect=responses),
        patch.object(opensky.tokens, "invalidate") as invalidate,
    ):
        states, _ = opensky.fetch_global_states()
    assert states == []
    invalidate.assert_called_once()


def test_client_errors_are_not_retried():
    with patch.object(opensky.requests, "get", return_value=_response(404)) as get:
        states, info = opensky.fetch_global_states()
    assert states is None and info["status"] == "api_error"
    assert get.call_count == 1


def test_missing_credentials_are_a_config_error_not_a_retry_loop():
    with (
        patch.object(opensky.tokens, "headers", side_effect=RuntimeError("no creds")),
        patch.object(opensky.requests, "get") as get,
    ):
        states, info = opensky.fetch_global_states()
    assert states is None and info["status"] == "config_error"
    get.assert_not_called()


# --------------------------------------------------- per-airport assembly
def test_a_failed_request_marks_every_airport_with_the_reason():
    with patch.object(opensky, "fetch_global_states",
                      return_value=(None, {"status": "rate_limited", "message": "quota",
                                           "attempts": 1, "credits_remaining": 0})):
        counts = opensky.fetch_all_airport_counts()
    assert all(counts[c] == 0 for c in AIRPORTS)
    assert {m["status"] for m in counts["_metadata"].values()} == {"rate_limited"}
    assert counts["_run"]["status"] == "rate_limited"
    assert counts["_run"]["aircraft_worldwide"] is None


def test_empty_boxes_are_flagged_no_states_not_ok():
    """Zero aircraft may be a coverage gap, so it must not read as a quiet airport."""
    atl = AIRPORTS["ATL"]
    with patch.object(opensky, "fetch_global_states",
                      return_value=([_state(atl.lon, atl.lat)],
                                    {"status": "ok", "attempts": 1, "credits_remaining": 3990, "api_time": 1})):
        counts = opensky.fetch_all_airport_counts()
    assert counts["_metadata"]["ATL"]["status"] == "ok"
    assert counts["_metadata"]["PVG"]["status"] == "no_states"
    assert counts["_run"]["aircraft_worldwide"] == 1


# ------------------------------------------------------------ weather batch
def _location(wind):
    return {"current": {"wind_speed_10m": wind, "wind_gusts_10m": 0, "precipitation": 0,
                        "cloud_cover": 0, "visibility": 20000, "weather_code": 0}}


def test_weather_batch_maps_results_to_airports_in_order():
    codes = list(weather.AIRPORT_COORDS)
    payload = [_location(i) for i in range(len(codes))]
    with patch.object(weather.requests, "get", return_value=_response(200, payload)):
        result = weather.fetch_all_weather()
    assert [result[c]["wind_speed_kn"] for c in codes] == list(range(len(codes)))


def test_weather_batch_with_the_wrong_length_yields_no_penalty_rather_than_misaligned_data():
    """Shifting results by one would assign Denver's storm to Dallas. Better none."""
    with patch.object(weather.requests, "get", return_value=_response(200, [_location(1)] * 3)):
        result = weather.fetch_all_weather()
    assert all(v == {} for v in result.values())


def test_weather_batch_failure_yields_empty_entries():
    with patch.object(weather.requests, "get", side_effect=requests.Timeout("slow")):
        result = weather.fetch_all_weather()
    assert set(result) == set(AIRPORTS)
    assert all(v == {} for v in result.values())
