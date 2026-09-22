"""Boundary behaviour of the weather capacity penalty."""

from __future__ import annotations

import pytest

from skylens.pipeline.scorer import weather_penalty

CLEAR = {"wind_speed_kn": 0, "wind_gusts_kn": 0, "precipitation_mm": 0, "visibility_m": 20000}


def w(**overrides):
    return {**CLEAR, **overrides}


def test_clear_conditions_have_no_penalty():
    assert weather_penalty(w()) == 1.0


def test_missing_weather_is_not_penalised():
    """An empty dict is what a failed Open-Meteo call returns.

    Regression: the visibility default of 10000m sits inside the "< 15000" band,
    so an absent reading used to cost a 0.05 penalty and inflate the score.
    Unknown conditions must not be scored as bad ones.
    """
    assert weather_penalty({}) == 1.0


@pytest.mark.parametrize(
    ("wind", "expected"),
    [(15, 1.0), (15.1, 0.95), (20, 0.95), (20.1, 0.85), (30, 0.85), (30.1, 0.75)],
)
def test_wind_thresholds_are_exclusive(wind, expected):
    """Each band triggers strictly above its threshold, not at it."""
    assert weather_penalty(w(wind_speed_kn=wind)) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("precip", "expected"), [(0, 1.0), (0.1, 0.95), (1, 0.95), (1.1, 0.85), (5, 0.85), (5.1, 0.75)]
)
def test_precipitation_thresholds(precip, expected):
    assert weather_penalty(w(precipitation_mm=precip)) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("vis", "expected"),
    [(20000, 1.0), (15000, 1.0), (14999, 0.95), (8000, 0.95), (7999, 0.90),
     (3000, 0.90), (2999, 0.75)],
)
def test_visibility_thresholds(vis, expected):
    assert weather_penalty(w(visibility_m=vis)) == pytest.approx(expected)


def test_penalty_never_drops_below_half():
    """Severe on every axis would sum past 0.5; the floor must hold."""
    severe = w(wind_speed_kn=60, wind_gusts_kn=80, precipitation_mm=50, visibility_m=100)
    assert weather_penalty(severe) == 0.5


def test_gusts_alone_can_trigger_a_penalty():
    """Gusts are evaluated independently of sustained wind."""
    assert weather_penalty(w(wind_gusts_kn=45)) == pytest.approx(0.75)
