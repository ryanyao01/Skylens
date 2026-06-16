from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from pathlib import Path
import json
import sys
import os

sys.path.append(str(Path(__file__).resolve().parents[1] / "pipeline"))

from opensky import fetch_all_airport_counts
from weather import fetch_all_weather
from scorer import load_models, compute_scores


app = FastAPI(title="SkyLens API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



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

# in-memory score cache
score_cache = {}
models = None

def refresh_scores():
    global score_cache
    try:
        flight_counts = fetch_all_airport_counts()
        weather = fetch_all_weather()
        scores = compute_scores(models, flight_counts, weather)
        # merge coordinates
        for icao, data in scores.items():
            coords = AIRPORT_COORDS.get(icao, {})
            scores[icao] = {**data, **coords}
        score_cache = scores
        print(f"scores refreshed — {len(scores)} airports")
    except Exception as e:
        print(f"score refresh failed: {e}")

@app.on_event("startup")
def startup():
    global models
    models = load_models()
    refresh_scores()  # run immediately on startup
    scheduler = BackgroundScheduler()
    scheduler.add_job(refresh_scores, "interval", seconds=60)
    scheduler.start()

@app.get("/airports/scores")
def get_scores():
    if score_cache:
        return score_cache
    return {"error": "scores not yet computed"}

@app.get("/airports/{icao}/score")
def get_airport_score(icao: str):
    if icao.upper() in score_cache:
        return score_cache[icao.upper()]
    return {"error": f"airport {icao} not found"}

@app.get("/health")
def health():
    return {"status": "ok", "airports_cached": len(score_cache)}

@app.get("/forecast/cascade")
def get_cascade():
    cascade_path = PROJECT_ROOT / "data" / "clean" / "cascade_forecast.json"
    if cascade_path.exists():
        with open(cascade_path) as f:
            return json.load(f)
    return {"error": "cascade forecast not yet computed"}

@app.get("/forecast/cascade/{icao}")
def get_airport_cascade(icao: str):
    cascade_path = PROJECT_ROOT / "data" / "clean" / "cascade_forecast.json"
    if cascade_path.exists():
        with open(cascade_path) as f:
            data = json.load(f)
        if icao.upper() in data:
            return data[icao.upper()]
    return {"error": f"no cascade data for {icao}"}