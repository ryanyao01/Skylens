"""Delay-cascade simulation."""

from __future__ import annotations

from skylens.pipeline.cascade import (
    CASCADE_THRESHOLD,
    run_all_cascades,
    simulate_cascade,
)

PROPAGATION = {"AAA": {"BBB": 0.5, "CCC": 0.2}, "BBB": {"DDD": 0.4}}


def _scores(aaa: float) -> dict:
    return {c: {"score": s} for c, s in [("AAA", aaa), ("BBB", 10), ("CCC", 10), ("DDD", 10)]}


def test_below_threshold_produces_no_cascade():
    result = simulate_cascade("AAA", _scores(CASCADE_THRESHOLD - 0.1), PROPAGATION)
    assert all(not hour for hour in result.values())


def test_at_threshold_cascades():
    """The trigger is >= threshold, so exactly 65.0 must cascade."""
    result = simulate_cascade("AAA", _scores(CASCADE_THRESHOLD), PROPAGATION)
    assert result[1], "an airport exactly at the threshold should propagate"


def test_downstream_airports_are_reached_in_wave_order():
    result = simulate_cascade("AAA", _scores(90), PROPAGATION)
    assert set(result[1]) == {"BBB", "CCC"}   # direct neighbours first
    assert "DDD" in result[2]                 # two hops away on the second wave


def test_an_airport_is_never_revisited():
    """`visited` guards against a node being impacted twice."""
    result = simulate_cascade("AAA", _scores(100), PROPAGATION)
    seen = [a for hour in result.values() for a in hour]
    assert len(seen) == len(set(seen))


def test_impact_is_capped():
    result = simulate_cascade("AAA", _scores(100), PROPAGATION)
    assert all(v <= 50.0 for hour in result.values() for v in hour.values())


def test_unknown_trigger_airport_is_safe():
    assert all(not h for h in simulate_cascade("ZZZ", _scores(100), PROPAGATION).values())


def test_run_all_cascades_only_includes_triggering_airports():
    scores = {
        "AAA": {"score": 90.0},                      # above
        "BBB": {"score": CASCADE_THRESHOLD},         # exactly at
        "CCC": {"score": CASCADE_THRESHOLD - 0.1},   # just below
    }
    assert set(run_all_cascades(scores, PROPAGATION)) == {"AAA", "BBB"}
