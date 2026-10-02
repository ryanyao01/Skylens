"""Shared fixtures. Tests never touch the network or mutate real state files."""

from __future__ import annotations

import time

import pytest

from skylens.airports import AIRPORTS as AIRPORT_TABLE
from skylens.config import settings

AIRPORTS = list(AIRPORT_TABLE)


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Point all runtime state -- peak observations, the warehouse -- at a temp dir.

    Without this, any test that boots the app would write a DuckDB file and
    peak observations into the real data/clean directory.
    """
    from skylens import warehouse

    monkeypatch.setattr(settings, "state_dir", tmp_path, raising=False)
    warehouse.close_warehouse()
    yield tmp_path
    warehouse.close_warehouse()


@pytest.fixture(scope="session")
def models():
    """The real pickled quantile models plus the JSON label encoder."""
    from skylens.pipeline.scorer import load_models

    return load_models()


@pytest.fixture
def flight_counts():
    """The shape fetch_all_airport_counts() returns after a successful request."""
    now = time.time()
    counts = dict.fromkeys(AIRPORTS, 30)
    counts["_metadata"] = {
        code: {"status": "ok", "message": "", "api_time": now} for code in AIRPORTS
    }
    counts["_run"] = {
        "source": "opensky_global",
        "status": "ok",
        "attempts": 1,
        "credits_remaining": 3_900,
        "aircraft_worldwide": 11_000,
        "elapsed_s": 2.0,
    }
    counts["timestamp"] = "2026-01-01T00:00:00+00:00"
    return counts


@pytest.fixture
def weather():
    return {
        code: {
            "wind_speed_kn": 5,
            "wind_gusts_kn": 8,
            "precipitation_mm": 0,
            "visibility_m": 20000,
        }
        for code in AIRPORTS
    }


@pytest.fixture
def peak_observations():
    return {code: {"peak": 60, "observations": 5} for code in AIRPORTS}
