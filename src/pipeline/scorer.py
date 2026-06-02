import pickle
import numpy as np
from datetime import datetime, timezone
from opensky import fetch_all_airport_counts
from weather import fetch_all_weather

import os
from pathlib import Path

# get the project root regardless of where script is run from
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = PROJECT_ROOT / "models"

def load_models():
    models = {}
    for q in ["q10", "q50", "q90"]:
        path = MODELS_DIR / f"xgb_{q}.pkl"
        with open(path, "rb") as f:
            models[q] = pickle.load(f)
    with open(MODELS_DIR / "label_encoder.pkl", "rb") as f:
        models["le"] = pickle.load(f)
    return models

# historical mean per airport/hour/day — your baseline feature
HIST_MEANS = {
    "ATL": 2.8, "DFW": 2.4, "ORD": 2.2, "DEN": 2.1,
    "CLT": 1.8, "LAX": 2.3, "LAS": 1.9, "LGA": 1.7,
    "SEA": 1.8, "PHX": 1.9
}

# peak capacity per airport from your model output
PEAK_CAPACITY = {
    "ATL": 4.8, "DFW": 4.5, "ORD": 4.2, "DEN": 4.0,
    "CLT": 3.5, "LAX": 4.3, "LAS": 3.6, "LGA": 3.4,
    "SEA": 3.7, "PHX": 3.6
}

LIVE_PEAK_COUNTS = {
    "ATL": 120, "DFW": 100, "ORD": 90, "DEN": 85,
    "CLT": 50, "LAX": 80, "LAS": 70, "LGA": 70,
    "SEA": 65, "PHX": 65
}

def weather_penalty(w: dict) -> float:
    """
    Returns a multiplier 0.5-1.0
    1.0 = perfect conditions, no penalty
    0.5 = severe conditions, capacity halved
    """
    penalty = 1.0
    
    wind = w.get("wind_speed_kn", 0)
    precip = w.get("precipitation_mm", 0)
    vis = w.get("visibility_m", 10000)
    gusts = w.get("wind_gusts_kn", 0)

    # wind penalties
    if wind > 30 or gusts > 40:
        penalty -= 0.25
    elif wind > 20 or gusts > 30:
        penalty -= 0.15
    elif wind > 15:
        penalty -= 0.05

    # precipitation penalties
    if precip > 5:
        penalty -= 0.25
    elif precip > 1:
        penalty -= 0.15
    elif precip > 0:
        penalty -= 0.05

    # visibility penalties
    if vis < 3000:
        penalty -= 0.25
    elif vis < 8000:
        penalty -= 0.10
    elif vis < 15000:
        penalty -= 0.05

    return max(penalty, 0.5)

def compute_scores(models: dict, 
                   flight_counts: dict, 
                   weather: dict) -> dict:
    now = datetime.now(timezone.utc)
    hour = now.hour
    minute = now.minute
    block = minute // 15
    dow = now.weekday() + 1
    month = now.month
    is_weekend = 1 if dow >= 6 else 0

    scores = {}

    for airport in HIST_MEANS:
        hist_mean = HIST_MEANS[airport]
        airport_enc = models["le"].transform([airport])[0]

        features = np.array([[
            hour,
            block,
            dow,
            month,
            is_weekend,
            hist_mean,
            airport_enc
        ]])

        pred_q50 = models["q50"].predict(features)[0]
        pred_q50 = max(pred_q50, 0.5)

        # weather adjustment
        w = weather.get(airport, {})
        penalty = weather_penalty(w)
        adjusted_capacity = pred_q50 * penalty

        # live flight count as demand proxy
        live_count = flight_counts.get(airport, 0)
        peak_count = LIVE_PEAK_COUNTS[airport]
        effective_peak = peak_count * penalty
        raw_score = (live_count / effective_peak) * 100
        score = min(round(raw_score, 1), 100)

        scores[airport] = {
            "score": float(score),
            "live_flights": int(live_count),
            "pred_capacity": float(round(adjusted_capacity, 2)),
            "weather_penalty": float(round(penalty, 2)),
            "wind_kn": float(w.get("wind_speed_kn", 0)),
            "precip_mm": float(w.get("precipitation_mm", 0)),
            "visibility_m": float(w.get("visibility_m", 10000)),
            "timestamp": now.isoformat()
        }

    return scores

if __name__ == "__main__":
    print("loading models...")
    models = load_models()

    print("fetching live data...")
    flight_counts = fetch_all_airport_counts()
    weather = fetch_all_weather()

    print("computing scores...")
    scores = compute_scores(models, flight_counts, weather)

    print("\n--- live imbalance scores ---")
    for airport, data in sorted(scores.items(), 
                                 key=lambda x: x[1]["score"], 
                                 reverse=True):
        bar = "█" * int(data["score"] / 5)
        print(f"{airport}  {data['score']:5.1f}  {bar}")
        print(f"       flights={data['live_flights']} "
              f"capacity={data['pred_capacity']} "
              f"weather={data['weather_penalty']} "
              f"wind={data['wind_kn']}kn")
        
    import json
    from pathlib import Path

    output_path = PROJECT_ROOT / "data" / "clean" / "live_scores.json"
    with open(output_path, "w") as f:
        json.dump(scores, f, indent=2)
    print(f"\nscores saved to {output_path}")