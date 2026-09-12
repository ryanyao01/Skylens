"""Offline: build the airport runtime profile consumed by the scorer.

Development-only tooling. Requires the ``offline`` extra (polars) and the
parquet files under ``data/clean``; the API never imports this module.
"""

from __future__ import annotations

import json
import statistics

import polars as pl

from skylens.config import settings

OUT = settings.airport_profile_file

model = pl.read_parquet(settings.clean_data_path / "model_ready.parquet")
imbalance = pl.read_parquet(settings.clean_data_path / "imbalance_scores.parquet")

hist_rows = (
    model.group_by(["DEST", "arr_hour", "day_of_week"])
    .agg(pl.col("hist_mean_arrivals").mean().round(6).alias("hist_mean"))
    .sort(["DEST", "day_of_week", "arr_hour"])
    .iter_rows(named=True)
)

default_hist = {
    row["DEST"]: float(row["hist_mean_arrivals"])
    for row in model.group_by("DEST")
    .agg(pl.col("hist_mean_arrivals").mean().round(6))
    .iter_rows(named=True)
}

peak_capacity = {
    row["DEST"]: float(row["peak_capacity"])
    for row in imbalance.group_by("DEST")
    .agg(pl.col("peak_capacity").first().round(6))
    .iter_rows(named=True)
}

hist_by_slot = {}
for row in hist_rows:
    key = f"{row['DEST']}|{int(row['day_of_week'])}|{int(row['arr_hour'])}"
    hist_by_slot[key] = float(row["hist_mean"])

INTERNATIONAL_FALLBACKS = {
    "HND": {"hist_mean_arrivals": 3.8, "peak_capacity": 7.0,
            "note": "Manual fallback: no training history; sized from public Haneda movement stats."},
    "NRT": {"hist_mean_arrivals": 3.0, "peak_capacity": 5.8,
            "note": "Manual fallback: no training history; sized from public Narita movement stats."},
    "KIX": {"hist_mean_arrivals": 1.8, "peak_capacity": 3.5,
            "note": "Manual fallback: no training history; smaller of the two Osaka-area international hubs."},
    "PVG": {"hist_mean_arrivals": 3.2, "peak_capacity": 6.2,
            "note": "Manual fallback: no training history; major China international hub."},
    "LHR": {"hist_mean_arrivals": 3.9, "peak_capacity": 7.3,
            "note": "Manual fallback: no training history; one of the world's busiest international hubs."},
    "CDG": {"hist_mean_arrivals": 3.4, "peak_capacity": 6.5,
            "note": "Manual fallback: no training history; major European hub."},
    "FRA": {"hist_mean_arrivals": 3.2, "peak_capacity": 6.2,
            "note": "Manual fallback: no training history; major European hub."},
    "AMS": {"hist_mean_arrivals": 2.9, "peak_capacity": 5.6,
            "note": "Manual fallback: no training history; major European hub."},
    "DXB": {"hist_mean_arrivals": 3.5, "peak_capacity": 6.8,
            "note": "Manual fallback: no training history; major Middle East hub."},
    "SIN": {"hist_mean_arrivals": 2.6, "peak_capacity": 5.0,
            "note": "Manual fallback: no training history; major Southeast Asia hub."},
    "ICN": {"hist_mean_arrivals": 2.9, "peak_capacity": 5.6,
            "note": "Manual fallback: no training history; major East Asia hub."},
    "SYD": {"hist_mean_arrivals": 2.2, "peak_capacity": 4.3,
            "note": "Manual fallback: no training history; primary Australian gateway."},
    "YYZ": {"hist_mean_arrivals": 2.7, "peak_capacity": 5.2,
            "note": "Manual fallback: no training history; primary Canadian gateway alongside YVR."},
}

INTERNATIONAL_LIVE_PEAK_COUNTS = {
    "HND": 100, "NRT": 85, "KIX": 55, "PVG": 90,
    "LHR": 110, "CDG": 95, "FRA": 90, "AMS": 80,
    "DXB": 100, "SIN": 75, "ICN": 85, "SYD": 65, "YYZ": 80,
}

# --- live peak counts -------------------------------------------------------
# The score denominator is an OpenSky *density* peak (aircraft inside a bounding
# box), but the trained models predict *arrivals per 15-minute slot*. These are
# different units, which is why a handful of density peaks were originally set
# by hand and every other airport fell back to a flat constant.
#
# Those hand-set values are observations, so they can calibrate the conversion:
# fit density_peak ~= k * model_peak_capacity on the airports where both exist,
# then use k to derive a per-airport density peak for everyone else. This is
# what makes the trained q90 capacity estimates actually reach the live score.
OBSERVED_LIVE_PEAK_COUNTS = {
    "ATL": 120, "DFW": 100, "ORD": 90, "DEN": 85, "CLT": 50,
    "LAX": 80, "LAS": 70, "LGA": 70, "SEA": 65, "PHX": 65,
    "YOW": 30, "YVR": 90,
}

_anchor_ratios = [
    OBSERVED_LIVE_PEAK_COUNTS[code] / peak_capacity[code]
    for code in OBSERVED_LIVE_PEAK_COUNTS
    if code in peak_capacity and peak_capacity[code] > 0
]
# Median, not mean: one hand-set anchor can be badly off without skewing the fit.
DENSITY_PER_ARRIVAL = round(statistics.median(_anchor_ratios), 3)

LIVE_PEAK_COUNTS = {
    code: max(int(round(capacity * DENSITY_PER_ARRIVAL)), 10)
    for code, capacity in peak_capacity.items()
}
# Directly observed values always win over the calibrated estimate.
LIVE_PEAK_COUNTS.update(OBSERVED_LIVE_PEAK_COUNTS)
LIVE_PEAK_COUNTS.update(INTERNATIONAL_LIVE_PEAK_COUNTS)
LIVE_PEAK_COUNTS = dict(sorted(LIVE_PEAK_COUNTS.items()))


profile = {
    "schema_version": 1,
    "generated_from": {
        "hist_mean": "data/clean/model_ready.parquet grouped by DEST, day_of_week, arr_hour",
        "peak_capacity": "data/clean/imbalance_scores.parquet peak_capacity from 95th percentile pred_q90",
        "live_peak_counts": (
            f"peak_capacity * {DENSITY_PER_ARRIVAL} (median density-per-arrival ratio fitted on "
            f"{len(_anchor_ratios)} observed anchors), overridden by direct observations where available"
        ),
    },
    "density_per_arrival": DENSITY_PER_ARRIVAL,
    "trained_airports": sorted(default_hist),
    "hist_mean_default": dict(sorted(default_hist.items())),
    "hist_mean_by_slot": hist_by_slot,
    "peak_capacity": dict(sorted(peak_capacity.items())),
    "live_peak_counts": LIVE_PEAK_COUNTS,
    "fallback_airports": {
        "YOW": {
            "hist_mean_arrivals": 1.2,
            "peak_capacity": 2.5,
            "note": "Manual fallback: no Kaggle training history; roughly sized from public YOW movement and passenger scale.",
        },
        "YVR": {
            "hist_mean_arrivals": 3.7,
            "peak_capacity": 6.0,
            "note": "Manual fallback: no Kaggle training history; roughly half of public YVR runway movement average, with busy-period headroom.",
        },
        **INTERNATIONAL_FALLBACKS,
    },
}
profile["live_peak_counts"].update(INTERNATIONAL_LIVE_PEAK_COUNTS)

OUT.write_text(json.dumps(profile, indent=2), encoding="utf-8")
print(f"Wrote {OUT}")
print(f"Hist slot rows: {len(hist_by_slot)}")
print(f"density_per_arrival k = {DENSITY_PER_ARRIVAL} (from {len(_anchor_ratios)} anchors)")
print(f"live_peak_counts: {len(LIVE_PEAK_COUNTS)} airports "
      f"({len(OBSERVED_LIVE_PEAK_COUNTS) + len(INTERNATIONAL_LIVE_PEAK_COUNTS)} observed, rest calibrated)")
