"""Peak-observation state: the only thing the service persists.

These values form the score denominator, so a corrupt or wrongly-updated file
silently shifts every airport's score.
"""

from __future__ import annotations

import json

import pytest

from skylens.config import settings
from skylens.pipeline import opensky


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "state_dir", tmp_path, raising=False)
    return tmp_path


def counts(**per_airport):
    payload = {code: {"count": n, "status": "ok"} for code, n in per_airport.items()}
    payload["_metadata"] = {code: {"status": "ok", "message": ""} for code in per_airport}
    payload["timestamp"] = "2026-01-01T00:00:00+00:00"
    return payload


def test_first_run_creates_the_file(state_dir):
    result = opensky.update_peak_observations(counts(ATL=40, ORD=30))
    assert result["ATL"] == {"peak": 40, "observations": 1}
    assert settings.peak_observations_file.exists()


def test_peak_only_ever_rises(state_dir):
    opensky.update_peak_observations(counts(ATL=40))
    opensky.update_peak_observations(counts(ATL=10))     # quieter
    result = opensky.update_peak_observations(counts(ATL=55))  # new high
    assert result["ATL"]["peak"] == 55
    assert result["ATL"]["observations"] == 3


def test_degraded_airports_do_not_record_a_peak(state_dir):
    """A no_states reading is missing data, not a real observation of zero."""
    payload = counts(ATL=40)
    payload["PVG"] = {"count": 0, "status": "no_states"}
    payload["_metadata"]["PVG"] = {"status": "no_states", "message": "no coverage"}
    result = opensky.update_peak_observations(payload)
    assert "PVG" not in result
    assert "ATL" in result


def test_metadata_and_timestamp_keys_are_not_treated_as_airports(state_dir):
    result = opensky.update_peak_observations(counts(ATL=40))
    assert set(result) == {"ATL"}


def test_state_survives_a_reload(state_dir):
    opensky.update_peak_observations(counts(ATL=40))
    assert opensky.load_peak_observations()["ATL"]["peak"] == 40


def test_a_corrupt_file_does_not_crash_the_refresh(state_dir):
    """Recover by starting fresh rather than taking the whole service down."""
    settings.peak_observations_file.write_text("{ this is not json", encoding="utf-8")
    assert opensky.load_peak_observations() == {}
    assert opensky.update_peak_observations(counts(ATL=40))["ATL"]["peak"] == 40


def test_writes_leave_no_temp_file_behind(state_dir):
    """Writes go to a .tmp then os.replace, so a crash cannot truncate the file."""
    opensky.update_peak_observations(counts(ATL=40))
    assert not list(state_dir.glob("*.tmp"))
    json.loads(settings.peak_observations_file.read_text(encoding="utf-8"))
