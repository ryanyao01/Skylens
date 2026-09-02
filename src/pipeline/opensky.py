import requests
import time
from datetime import datetime
from datetime import timedelta
import json
from pathlib import Path

import os
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
CLIENT_ID = os.getenv("OPENSKY_CLIENT_ID")
CLIENT_SECRET = os.getenv("OPENSKY_CLIENT_SECRET")
TOKEN_REFRESH_MARGIN = 30  # seconds before expiration to refresh the token

class TokenManager:
    def __init__(self):
        self.token = None
        self.expires_at = None

    def get_token(self):
        if self.token and self.expires_at and datetime.utcnow() < self.expires_at:
            return self.token
        return self._refresh()

    def _refresh(self):
        r = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
        r.raise_for_status()
        data = r.json()
        self.token = data["access_token"]
        expires_in = data.get("expires_in", 1800)
        self.expires_at = datetime.utcnow() + timedelta(seconds=expires_in - TOKEN_REFRESH_MARGIN)
        return self.token

    def headers(self):
        return {"Authorization": f"Bearer {self.get_token()}"}


tokens = TokenManager()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OBSERVATIONS_PATH = PROJECT_ROOT / "data" / "clean" / "live_peak_observations.json"

def load_peak_observations() -> dict:
    try:
        with open(OBSERVATIONS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def update_peak_observations(counts: dict) -> dict:
    observations = load_peak_observations()
    metadata = counts.get("_metadata", {})
    for airport, count in counts.items():
        if airport == "timestamp" or airport.startswith("_"):
            continue
        status = metadata.get(airport, {}).get("status")
        if status and status != "ok":
            continue
        count = extract_count(count)
        if airport not in observations:
            observations[airport] = {"peak": 0, "observations": 0}
        if count > observations[airport]["peak"]:
            observations[airport]["peak"] = count
        observations[airport]["observations"] += 1
    with open(OBSERVATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(observations, f, indent=2)
    return observations

OPENSKY_URL = "https://opensky-network.org/api/states/all"

# tracked airports with their approximate bounding boxes
# format: [lat_min, lat_max, lon_min, lon_max]
AIRPORT_BOUNDS = {
    # US expansion
    "ATL": [33.3, 34.0, -85.0, -84.0],
    "DFW": [32.6, 33.2, -97.5, -96.8],
    "ORD": [41.7, 42.1, -88.0, -87.6],
    "DEN": [39.7, 40.0, -105.0, -104.5],
    "CLT": [35.1, 35.5, -81.0, -80.6],
    "LAX": [33.8, 34.1, -118.6, -118.2],
    "LAS": [36.0, 36.3, -115.3, -114.9],
    "LGA": [40.7, 40.9, -74.0, -73.7],
    "SEA": [47.1, 47.9, -122.7, -121.9],
    "PHX": [33.3, 33.6, -112.3, -111.9],
    "YOW": [45.1, 45.5, -75.9, -75.4],
    "YVR": [49.0, 49.4, -123.4, -122.9],
    "JFK": [40.34, 40.94, -74.13, -73.43],
    "MIA": [25.50, 26.10, -80.64, -79.94],
    "BOS": [42.06, 42.66, -71.36, -70.66],
    "MSP": [44.58, 45.18, -93.57, -92.87],
    "DTW": [41.91, 42.51, -83.70, -83.00],
    "PHL": [39.57, 40.17, -75.59, -74.89],
    "BWI": [38.88, 39.48, -77.02, -76.32],
    "SLC": [40.49, 41.09, -112.33, -111.63],
    "SAN": [32.43, 33.03, -117.54, -116.84],
    "IAD": [38.64, 39.24, -77.81, -77.11],
    "STL": [38.45, 39.05, -90.72, -90.02],
    "MCI": [39.00, 39.60, -95.06, -94.36],
    "CVG": [38.75, 39.35, -85.02, -84.32],
    "IND": [39.42, 40.02, -86.64, -85.94],
    "CLE": [41.11, 41.71, -82.20, -81.50],
    "PIT": [40.19, 40.79, -80.58, -79.88],
    "MKE": [42.65, 43.25, -88.25, -87.55],
    "RDU": [35.58, 36.18, -79.14, -78.44],
    "AUS": [29.90, 30.50, -98.01, -97.31],
    "SAT": [29.23, 29.83, -98.82, -98.12],
    "MDW": [41.49, 42.09, -88.10, -87.40],
    "TPA": [27.68, 28.28, -82.88, -82.18],
    "MCO": [28.13, 28.73, -81.66, -80.96],
    "FLL": [25.77, 26.37, -80.50, -79.80],
    "DCA": [38.55, 39.15, -77.39, -76.69],
    "EWR": [40.39, 40.99, -74.52, -73.82],
    "HNL": [21.02, 21.62, -158.28, -157.58],
    "PDX": [45.29, 45.89, -122.95, -122.25],
    "SMF": [38.40, 39.00, -121.94, -121.24],
    "OAK": [37.42, 38.02, -122.57, -121.87],
    "SJC": [37.06, 37.66, -122.28, -121.58],
    "BNA": [35.82, 36.42, -87.03, -86.33],
    "MSY": [29.69, 30.29, -90.61, -89.91],
    # international Phase A
    "HND": [35.25, 35.85, 139.44, 140.14],
    "NRT": [35.47, 36.07, 140.04, 140.74],
    "KIX": [34.13, 34.73, 134.89, 135.59],
    "PVG": [30.84, 31.44, 121.46, 122.16],
    "LHR": [51.17, 51.77, -0.81, -0.11],
    "CDG": [48.71, 49.31, 2.20, 2.90],
    "FRA": [49.73, 50.33, 8.21, 8.91],
    "AMS": [52.01, 52.61, 4.41, 5.11],
    "DXB": [24.95, 25.55, 55.02, 55.72],
    "SIN": [1.05, 1.65, 103.64, 104.34],
    "ICN": [37.17, 37.77, 126.10, 126.80],
    "SYD": [-34.25, -33.65, 150.83, 151.53],
    "YYZ": [43.38, 43.98, -79.98, -79.28],
}


def extract_count(value) -> int:
    if isinstance(value, dict):
        return int(value.get("count", 0) or 0)
    return int(value or 0)


def fetch_airport_state_count(airport_code: str) -> dict:
    bounds = AIRPORT_BOUNDS[airport_code]
    params = {
        "lamin": bounds[0],
        "lamax": bounds[1],
        "lomin": bounds[2],
        "lomax": bounds[3],
    }
    try:
        response = requests.get(OPENSKY_URL, params=params, headers=tokens.headers(), timeout=10)
        if response.status_code != 200:
            message = f"OpenSky API returned HTTP {response.status_code}"
            print(f"{airport_code}: {message}")
            return {
                "count": 0,
                "status": "api_error",
                "message": message,
            }

        data = response.json()
        states = data.get("states")
        if states is None:
            return {
                "count": 0,
                "status": "no_states",
                "message": (
                    "OpenSky returned no state vectors for this bounding box; "
                    "this can mean true inactivity or incomplete receiver coverage."
                ),
                "api_time": data.get("time"),
            }

        return {
            "count": len(states),
            "status": "ok",
            "message": "OpenSky returned state vectors for this bounding box.",
            "api_time": data.get("time"),
        }
    except Exception as e:
        message = str(e)
        print(f"{airport_code}: {message}")
        return {
            "count": 0,
            "status": "network_error",
            "message": message,
        }

def fetch_flights_near_airport(airport_code: str) -> int:
    return fetch_airport_state_count(airport_code)["count"]

def fetch_all_airport_counts() -> dict:
    counts = {}
    metadata = {}
    for airport in AIRPORT_BOUNDS:
        result = fetch_airport_state_count(airport)
        counts[airport] = result["count"]
        metadata[airport] = {
            key: value
            for key, value in result.items()
            if key != "count"
        }
        time.sleep(0.5)  # avoid rate limiting
    counts["timestamp"] = datetime.utcnow().isoformat()
    counts["_metadata"] = metadata
    return counts

if __name__ == "__main__":
    print("fetching live flight counts...")
    counts = fetch_all_airport_counts()
    for k, v in counts.items():
        print(f"{k}: {v}")
