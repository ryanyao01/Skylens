from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import os

app = FastAPI(title="SkyLens API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# airport coordinates for globe rendering
AIRPORT_COORDS = {
    "ATL": {"lat": 33.6407, "lon": -84.4277, "name": "Atlanta"},
    "DFW": {"lat": 32.8998, "lon": -97.0403, "name": "Dallas Fort Worth"},
    "ORD": {"lat": 41.9742, "lon": -87.9073, "name": "Chicago O'Hare"},
    "DEN": {"lat": 39.8561, "lon": -104.6737, "name": "Denver"},
    "CLT": {"lat": 35.2140, "lon": -80.9431, "name": "Charlotte"},
    "LAX": {"lat": 33.9425, "lon": -118.4081, "name": "Los Angeles"},
    "LAS": {"lat": 36.0840, "lon": -115.1537, "name": "Las Vegas"},
    "LGA": {"lat": 40.7772, "lon": -73.8726, "name": "New York LaGuardia"},
    "SEA": {"lat": 47.4502, "lon": -122.3088, "name": "Seattle"},
    "PHX": {"lat": 33.4373, "lon": -112.0078, "name": "Phoenix"},
    "YVR": {"lat": 49.1967, "lon": -123.1815, "name": "Vancouver"},
    "YOW": {"lat": 45.3225, "lon": -75.6692, "name": "Ottawa"},
}

@app.get("/airports/scores")
def get_scores():
    scores_path = PROJECT_ROOT / "data" / "clean" / "live_scores.json"
    if scores_path.exists():
        with open(scores_path) as f:
            scores = json.load(f)
        # merge coordinates into each airport's data
        result = {}
        for icao, data in scores.items():
            coords = AIRPORT_COORDS.get(icao, {})
            result[icao] = {**data, **coords}
        return result
    return {"error": "scores not yet computed"}

@app.get("/airports/{icao}/score")
def get_airport_score(icao: str):
    scores_path = PROJECT_ROOT / "data" / "clean" / "live_scores.json"
    if scores_path.exists():
        with open(scores_path) as f:
            scores = json.load(f)
        if icao.upper() in scores:
            return scores[icao.upper()]
    return {"error": f"airport {icao} not found"}

@app.get("/health")
def health():
    return {"status": "ok"}