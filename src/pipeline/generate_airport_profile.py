from pathlib import Path
import json

import polars as pl


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "clean" / "airport_runtime_profile.json"

model = pl.read_parquet(ROOT / "data" / "clean" / "model_ready.parquet")
imbalance = pl.read_parquet(ROOT / "data" / "clean" / "imbalance_scores.parquet")

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

profile = {
    "schema_version": 1,
    "generated_from": {
        "hist_mean": "data/clean/model_ready.parquet grouped by DEST, day_of_week, arr_hour",
        "peak_capacity": "data/clean/imbalance_scores.parquet peak_capacity from 95th percentile pred_q90",
    },
    "trained_airports": sorted(default_hist),
    "hist_mean_default": dict(sorted(default_hist.items())),
    "hist_mean_by_slot": hist_by_slot,
    "peak_capacity": dict(sorted(peak_capacity.items())),
    "live_peak_counts": {
        "ATL": 120,
        "DFW": 100,
        "ORD": 90,
        "DEN": 85,
        "CLT": 50,
        "LAX": 80,
        "LAS": 70,
        "LGA": 70,
        "SEA": 65,
        "PHX": 65,
        "YOW": 30,
        "YVR": 90,
    },
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
    },
}

OUT.write_text(json.dumps(profile, indent=2), encoding="utf-8")
print(f"Wrote {OUT}")
print(f"Hist slot rows: {len(hist_by_slot)}")
