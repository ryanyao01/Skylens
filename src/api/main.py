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
from cascade import load_propagation, run_all_cascades


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
    "JFK": {"lat": 40.6394, "lon": -73.7793, "name": "New York JFK"},
    "MIA": {"lat": 25.7960, "lon": -80.2898, "name": "Miami"},
    "BOS": {"lat": 42.3620, "lon": -71.0079, "name": "Boston"},
    "MSP": {"lat": 44.8801, "lon": -93.2217, "name": "Minneapolis"},
    "DTW": {"lat": 42.2138, "lon": -83.3538, "name": "Detroit"},
    "PHL": {"lat": 39.8719, "lon": -75.2411, "name": "Philadelphia"},
    "BWI": {"lat": 39.1754, "lon": -76.6683, "name": "Baltimore"},
    "SLC": {"lat": 40.7889, "lon": -111.9799, "name": "Salt Lake City"},
    "SAN": {"lat": 32.7336, "lon": -117.1900, "name": "San Diego"},
    "IAD": {"lat": 38.9445, "lon": -77.4558, "name": "Washington Dulles"},
    "STL": {"lat": 38.7487, "lon": -90.3700, "name": "St. Louis"},
    "MCI": {"lat": 39.3017, "lon": -94.7139, "name": "Kansas City"},
    "CVG": {"lat": 39.0488, "lon": -84.6678, "name": "Cincinnati"},
    "IND": {"lat": 39.7173, "lon": -86.2944, "name": "Indianapolis"},
    "CLE": {"lat": 41.4117, "lon": -81.8498, "name": "Cleveland"},
    "PIT": {"lat": 40.4915, "lon": -80.2329, "name": "Pittsburgh"},
    "MKE": {"lat": 42.9472, "lon": -87.8966, "name": "Milwaukee"},
    "RDU": {"lat": 35.8787, "lon": -78.7873, "name": "Raleigh-Durham"},
    "AUS": {"lat": 30.1975, "lon": -97.6620, "name": "Austin"},
    "SAT": {"lat": 29.5337, "lon": -98.4698, "name": "San Antonio"},
    "MDW": {"lat": 41.7860, "lon": -87.7524, "name": "Chicago Midway"},
    "TPA": {"lat": 27.9755, "lon": -82.5332, "name": "Tampa"},
    "MCO": {"lat": 28.4294, "lon": -81.3090, "name": "Orlando"},
    "FLL": {"lat": 26.0726, "lon": -80.1527, "name": "Fort Lauderdale"},
    "DCA": {"lat": 38.8521, "lon": -77.0377, "name": "Washington Reagan"},
    "EWR": {"lat": 40.6894, "lon": -74.1705, "name": "Newark"},
    "HNL": {"lat": 21.3184, "lon": -157.9257, "name": "Honolulu"},
    "PDX": {"lat": 45.5887, "lon": -122.5980, "name": "Portland"},
    "SMF": {"lat": 38.6954, "lon": -121.5910, "name": "Sacramento"},
    "OAK": {"lat": 37.7201, "lon": -122.2212, "name": "Oakland"},
    "SJC": {"lat": 37.3625, "lon": -121.9292, "name": "San Jose"},
    "BNA": {"lat": 36.1245, "lon": -86.6782, "name": "Nashville"},
    "MSY": {"lat": 29.9934, "lon": -90.2647, "name": "New Orleans"},
    "HND": {"lat": 35.5497, "lon": 139.7870, "name": "Tokyo Haneda"},
    "NRT": {"lat": 35.7686, "lon": 140.3887, "name": "Tokyo Narita"},
    "KIX": {"lat": 34.4273, "lon": 135.2440, "name": "Osaka Kansai"},
    "PVG": {"lat": 31.1434, "lon": 121.8050, "name": "Shanghai Pudong"},
    "LHR": {"lat": 51.4707, "lon": -0.4599, "name": "London Heathrow"},
    "CDG": {"lat": 49.0090, "lon": 2.5541, "name": "Paris Charles de Gaulle"},
    "FRA": {"lat": 50.0267, "lon": 8.5584, "name": "Frankfurt"},
    "AMS": {"lat": 52.3086, "lon": 4.7639, "name": "Amsterdam Schiphol"},
    "DXB": {"lat": 25.2498, "lon": 55.3710, "name": "Dubai"},
    "SIN": {"lat": 1.3502, "lon": 103.9940, "name": "Singapore Changi"},
    "ICN": {"lat": 37.4691, "lon": 126.4510, "name": "Seoul Incheon"},
    "SYD": {"lat": -33.9461, "lon": 151.1770, "name": "Sydney"},
    "YYZ": {"lat": 43.6759, "lon": -79.6294, "name": "Toronto Pearson"},
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
        
        propagation = load_propagation()
        cascades = run_all_cascades(scores, propagation)
        cascade_path = PROJECT_ROOT / "data" / "clean" / "cascade_forecast.json"
        with open(cascade_path, "w") as f:
            json.dump(cascades, f, indent=2)
        
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