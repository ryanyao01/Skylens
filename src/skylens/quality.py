"""Data-quality checks, run after every refresh and recorded in the warehouse.

Unit tests prove the *code* is right. These prove the *data* is: that the
upstream answered, that every airport is present, that values are in range,
that nothing is stale, and that this run looks like the last one. A failing
critical check means the run's output should not be trusted; a failing
warning means it is usable but degraded.

Every check here exists because of a failure mode this project has actually
had or would silently suffer:

    opensky_request_ok         the quota ran out at ~17h/day and nothing said so
    opensky_data_fresh         a cached or stalled upstream returns old vectors
    live_data_coverage         East Asian receiver coverage drops airports to 0
    aircraft_volume_plausible  HTTP 200 with a near-empty sky is still a failure
    aircraft_volume_stable     run-over-run swings that time of day cannot explain
"""

from __future__ import annotations

import math
from datetime import datetime

from skylens.airports import AIRPORTS

CRITICAL = "critical"
WARNING = "warning"

FRESHNESS_LIMIT_S = 600
MIN_LIVE_COVERAGE = 0.90
MAX_WEATHER_MISSING = 0.10
MIN_AIRCRAFT_WORLDWIDE = 3_000
MAX_RUN_OVER_RUN_CHANGE = 0.50
MIN_CREDITS = 400  # about one day of refreshes at 4 credits every 15 minutes


def _result(name: str, severity: str, passed: bool, observed, expectation: str) -> dict:
    return {
        "check_name": name,
        "severity": severity,
        "passed": bool(passed),
        "observed": observed,
        "expectation": expectation,
    }


def _is_valid_score(value) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and not math.isnan(value)
        and 0 <= value <= 100
    )


def run_checks(
    *,
    flight_counts: dict,
    weather: dict,
    scores: dict,
    now: datetime,
    previous_aircraft_total: int | None = None,
) -> list[dict]:
    run = flight_counts.get("_run", {})
    metadata = flight_counts.get("_metadata", {})
    total = len(AIRPORTS)
    results: list[dict] = []

    # --- the upstream request itself -------------------------------------
    results.append(_result(
        "opensky_request_ok", CRITICAL,
        run.get("status") == "ok",
        run.get("status", "unknown"),
        "upstream request status is ok",
    ))

    api_times = [m.get("api_time") for m in metadata.values() if m.get("api_time")]
    if api_times:
        age = now.timestamp() - max(api_times)
        results.append(_result(
            "opensky_data_fresh", CRITICAL, age <= FRESHNESS_LIMIT_S,
            f"{age:.0f}s old", f"upstream data at most {FRESHNESS_LIMIT_S // 60} minutes old",
        ))
    else:
        results.append(_result(
            "opensky_data_fresh", CRITICAL, False,
            "no data timestamp", f"upstream data at most {FRESHNESS_LIMIT_S // 60} minutes old",
        ))

    worldwide = run.get("aircraft_worldwide")
    results.append(_result(
        "aircraft_volume_plausible", WARNING,
        worldwide is not None and worldwide >= MIN_AIRCRAFT_WORLDWIDE,
        worldwide if worldwide is not None else "unknown",
        f"at least {MIN_AIRCRAFT_WORLDWIDE:,} aircraft visible worldwide",
    ))

    credits = run.get("credits_remaining")
    results.append(_result(
        "api_quota_headroom", WARNING,
        credits is None or credits >= MIN_CREDITS,
        credits if credits is not None else "unknown",
        f"at least {MIN_CREDITS} OpenSky credits left",
    ))

    # --- completeness and coverage ---------------------------------------
    results.append(_result(
        "all_airports_scored", CRITICAL,
        set(scores) == set(AIRPORTS),
        f"{len(scores)}/{total}",
        f"all {total} airports present",
    ))

    live = sum(1 for m in metadata.values() if m.get("status") == "ok")
    results.append(_result(
        "live_data_coverage", WARNING,
        live / total >= MIN_LIVE_COVERAGE,
        f"{live}/{total} airports",
        f"at least {MIN_LIVE_COVERAGE:.0%} of airports with live data",
    ))

    missing = sum(1 for code in AIRPORTS if not weather.get(code))
    results.append(_result(
        "weather_coverage", WARNING,
        missing <= total * MAX_WEATHER_MISSING,
        f"{missing} missing",
        f"at most {MAX_WEATHER_MISSING:.0%} of airports missing weather",
    ))

    # --- validity of what we computed ------------------------------------
    bad = sorted(code for code, d in scores.items() if not _is_valid_score(d.get("score")))
    results.append(_result(
        "score_in_range", CRITICAL, not bad,
        f"{len(bad)} invalid" + (f": {', '.join(bad[:5])}" if bad else ""),
        "every score is a number between 0 and 100",
    ))

    disordered = []
    for code, d in scores.items():
        f = d.get("forecast_next_hour") or {}
        quantiles = (f.get("p10"), f.get("p50"), f.get("p90"))
        if (
            d.get("forecast_source") == "model"
            and None not in quantiles
            and not quantiles[0] <= quantiles[1] <= quantiles[2]
        ):
            disordered.append(code)
    results.append(_result(
        "forecast_quantiles_ordered", WARNING, not disordered,
        f"{len(disordered)} disordered" + (f": {', '.join(sorted(disordered)[:5])}" if disordered else ""),
        "p10 <= p50 <= p90 for every modelled airport",
    ))

    # --- consistency with the previous run -------------------------------
    current = sum(
        flight_counts[code] for code in AIRPORTS if isinstance(flight_counts.get(code), int)
    )
    if previous_aircraft_total:
        change = abs(current - previous_aircraft_total) / previous_aircraft_total
        results.append(_result(
            "aircraft_volume_stable", WARNING, change <= MAX_RUN_OVER_RUN_CHANGE,
            f"{previous_aircraft_total} -> {current} ({change:+.0%})",
            f"tracked-airport total within {MAX_RUN_OVER_RUN_CHANGE:.0%} of the previous run",
        ))
    else:
        results.append(_result(
            "aircraft_volume_stable", WARNING, True, "no previous run to compare",
            f"tracked-airport total within {MAX_RUN_OVER_RUN_CHANGE:.0%} of the previous run",
        ))

    return results


def summarize(results: list[dict]) -> str:
    """'pass', 'warn' (only warnings failed) or 'fail' (a critical check failed)."""
    if any(not r["passed"] and r["severity"] == CRITICAL for r in results):
        return "fail"
    if any(not r["passed"] for r in results):
        return "warn"
    return "pass"
