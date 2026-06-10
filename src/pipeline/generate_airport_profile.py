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
