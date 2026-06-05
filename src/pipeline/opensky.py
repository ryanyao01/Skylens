import requests
import time
from datetime import datetime

OPENSKY_URL = "https://opensky-network.org/api/states/all"

# tracked airports with their approximate bounding boxes
# format: [lat_min, lat_max, lon_min, lon_max]
AIRPORT_BOUNDS = {
    "ATL": [33.3, 34.0, -85.0, -84.0],
    "DFW": [32.6, 33.2, -97.5, -96.8],
    "ORD": [41.7, 42.1, -88.0, -87.6],
    "DEN": [39.7, 40.0, -105.0, -104.5],
    "CLT": [35.1, 35.5, -81.0, -80.6],
    "LAX": [33.8, 34.1, -118.6, -118.2],
    "LAS": [36.0, 36.3, -115.3, -114.9],
    "LGA": [40.7, 40.9, -74.0, -73.7],
    "SEA": [47.3, 47.7, -122.5, -122.1],
    "PHX": [33.3, 33.6, -112.3, -111.9],
    "YOW": [45.1, 45.5, -75.9, -75.4],
    "YVR": [49.0, 49.4, -123.4, -122.9],
}

def fetch_flights_near_airport(airport_code: str) -> int:
    bounds = AIRPORT_BOUNDS[airport_code]
    params = {
        "lamin": bounds[0],
        "lamax": bounds[1],
        "lomin": bounds[2],
        "lomax": bounds[3]
    }
    try:
        response = requests.get(OPENSKY_URL, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            states = data.get("states", []) or []
            return len(states)
        else:
            print(f"{airport_code}: API error {response.status_code}")
            return 0
    except Exception as e:
        print(f"{airport_code}: {e}")
        return 0

def fetch_all_airport_counts() -> dict:
    counts = {}
    for airport in AIRPORT_BOUNDS:
        counts[airport] = fetch_flights_near_airport(airport)
        time.sleep(0.5)  # avoid rate limiting
    counts["timestamp"] = datetime.utcnow().isoformat()
    return counts

if __name__ == "__main__":
    print("fetching live flight counts...")
    counts = fetch_all_airport_counts()
    for k, v in counts.items():
        print(f"{k}: {v}")
