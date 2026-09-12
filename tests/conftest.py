"""Shared fixtures. Tests never touch the network or mutate real state files."""

from __future__ import annotations

import pytest

from skylens.pipeline.weather import AIRPORT_COORDS

AIRPORTS = list(AIRPORT_COORDS)


@pytest.fixture(scope="session")
def models():
    """The real pickled quantile models plus the JSON label encoder."""
    from skylens.pipeline.scorer import load_models

    return load_models()


@pytest.fixture
def flight_counts():
    counts = {code: {"count": 30, "status": "ok"} for code in AIRPORTS}
    counts["_metadata"] = {code: {"status": "ok", "message": ""} for code in AIRPORTS}
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
