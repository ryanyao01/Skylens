import requests
from datetime import datetime

# Open-Meteo free API - no key needed
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# airport coordinates
AIRPORT_COORDS = {
    "ATL": (33.6407, -84.4277), "DFW": (32.8998, -97.0403), "ORD": (41.9742, -87.9073),
    "DEN": (39.8561, -104.6737), "CLT": (35.2140, -80.9431), "LAX": (33.9425, -118.4081),
    "LAS": (36.0840, -115.1537), "LGA": (40.7772, -73.8726), "SEA": (47.4502, -122.3088),
    "PHX": (33.4373, -112.0078), "YOW": (45.3225, -75.6692), "YVR": (49.1967, -123.1815),
    "JFK": (40.6394, -73.7793), "MIA": (25.7960, -80.2898), "BOS": (42.3620, -71.0079),
    "MSP": (44.8801, -93.2217), "DTW": (42.2138, -83.3538), "PHL": (39.8719, -75.2411),
    "BWI": (39.1754, -76.6683), "SLC": (40.7889, -111.9799), "SAN": (32.7336, -117.1900),
    "IAD": (38.9445, -77.4558), "STL": (38.7487, -90.3700), "MCI": (39.3017, -94.7139),
    "CVG": (39.0488, -84.6678), "IND": (39.7173, -86.2944), "CLE": (41.4117, -81.8498),
    "PIT": (40.4915, -80.2329), "MKE": (42.9472, -87.8966), "RDU": (35.8787, -78.7873),
    "AUS": (30.1975, -97.6620), "SAT": (29.5337, -98.4698), "MDW": (41.7860, -87.7524),
    "TPA": (27.9755, -82.5332), "MCO": (28.4294, -81.3090), "FLL": (26.0726, -80.1527),
    "DCA": (38.8521, -77.0377), "EWR": (40.6894, -74.1705), "HNL": (21.3184, -157.9257),
    "PDX": (45.5887, -122.5980), "SMF": (38.6954, -121.5910), "OAK": (37.7201, -122.2212),
    "SJC": (37.3625, -121.9292), "BNA": (36.1245, -86.6782), "MSY": (29.9934, -90.2647),
    "HND": (35.5497, 139.7870), "NRT": (35.7686, 140.3887), "KIX": (34.4273, 135.2440),
    "PVG": (31.1434, 121.8050), "LHR": (51.4707, -0.4599), "CDG": (49.0090, 2.5541),
    "FRA": (50.0267, 8.5584), "AMS": (52.3086, 4.7639), "DXB": (25.2498, 55.3710),
    "SIN": (1.3502, 103.9940), "ICN": (37.4691, 126.4510), "SYD": (-33.9461, 151.1770),
    "YYZ": (43.6759, -79.6294),
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
