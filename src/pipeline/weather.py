import requests
from datetime import datetime

# Open-Meteo free API - no key needed
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# airport coordinates
AIRPORT_COORDS = {
    "ATL": (33.6407, -84.4277),
    "DFW": (32.8998, -97.0403),
    "ORD": (41.9742, -87.9073),
    "DEN": (39.8561, -104.6737),
    "CLT": (35.2140, -80.9431),
    "LAX": (33.9425, -118.4081),
    "LAS": (36.0840, -115.1537),
    "LGA": (40.7772, -73.8726),
    "SEA": (47.4502, -122.3088),
    "PHX": (33.4373, -112.0078),
    "YOW": (45.3225, -75.6692),
    "YVR": (49.1967, -123.1815),
}

def fetch_weather(airport_code: str) -> dict:
    lat, lon = AIRPORT_COORDS[airport_code]
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "wind_speed_10m",
            "wind_gusts_10m", 
            "precipitation",
            "cloud_cover",
            "visibility",
            "weather_code"
        ],
        "wind_speed_unit": "kn",
        "timezone": "UTC"
    }
    try:
        response = requests.get(WEATHER_URL, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            current = data["current"]
            return {
                "airport": airport_code,
                "wind_speed_kn": current.get("wind_speed_10m", 0),
                "wind_gusts_kn": current.get("wind_gusts_10m", 0),
                "precipitation_mm": current.get("precipitation", 0),
                "cloud_cover_pct": current.get("cloud_cover", 0),
                "visibility_m": current.get("visibility", 10000),
                "weather_code": current.get("weather_code", 0),
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            print(f"{airport_code}: weather API error {response.status_code}")
            return {}
    except Exception as e:
        print(f"{airport_code}: {e}")
        return {}

def fetch_all_weather() -> dict:
    weather = {}
    for airport in AIRPORT_COORDS:
        weather[airport] = fetch_weather(airport)
    return weather

if __name__ == "__main__":
    print("fetching live weather...")
    weather = fetch_all_weather()
    for airport, w in weather.items():
        print(f"{airport}: wind={w.get('wind_speed_kn')}kn "
              f"precip={w.get('precipitation_mm')}mm "
              f"cloud={w.get('cloud_cover_pct')}% "
              f"vis={w.get('visibility_m')}m")
