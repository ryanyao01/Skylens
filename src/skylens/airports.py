"""Reference data for every airport SkyLens tracks.

One table, one place. Coordinates position markers and weather lookups; the
IANA time zone converts "now" into the airport's local clock, which is the clock
the forecasting models were trained on (BTS ``CRS_ARR_TIME`` is local time).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Airport:
    code: str
    name: str
    lat: float
    lon: float
    tz: str

    def local_time(self, moment: datetime) -> datetime:
        """``moment`` (timezone-aware) on this airport's wall clock."""
        return moment.astimezone(ZoneInfo(self.tz))


AIRPORTS: dict[str, Airport] = {
    "ATL": Airport("ATL", "Atlanta", 33.6407, -84.4277, "America/New_York"),
    "DFW": Airport("DFW", "Dallas Fort Worth", 32.8998, -97.0403, "America/Chicago"),
    "ORD": Airport("ORD", "Chicago O'Hare", 41.9742, -87.9073, "America/Chicago"),
    "DEN": Airport("DEN", "Denver", 39.8561, -104.6737, "America/Denver"),
    "CLT": Airport("CLT", "Charlotte", 35.2140, -80.9431, "America/New_York"),
    "LAX": Airport("LAX", "Los Angeles", 33.9425, -118.4081, "America/Los_Angeles"),
    "LAS": Airport("LAS", "Las Vegas", 36.0840, -115.1537, "America/Los_Angeles"),
    "LGA": Airport("LGA", "New York LaGuardia", 40.7772, -73.8726, "America/New_York"),
    "SEA": Airport("SEA", "Seattle", 47.4502, -122.3088, "America/Los_Angeles"),
    "PHX": Airport("PHX", "Phoenix", 33.4373, -112.0078, "America/Phoenix"),
    "YVR": Airport("YVR", "Vancouver", 49.1967, -123.1815, "America/Vancouver"),
    "YOW": Airport("YOW", "Ottawa", 45.3225, -75.6692, "America/Toronto"),
    "JFK": Airport("JFK", "New York JFK", 40.6394, -73.7793, "America/New_York"),
    "MIA": Airport("MIA", "Miami", 25.7960, -80.2898, "America/New_York"),
    "BOS": Airport("BOS", "Boston", 42.3620, -71.0079, "America/New_York"),
    "MSP": Airport("MSP", "Minneapolis", 44.8801, -93.2217, "America/Chicago"),
    "DTW": Airport("DTW", "Detroit", 42.2138, -83.3538, "America/Detroit"),
    "PHL": Airport("PHL", "Philadelphia", 39.8719, -75.2411, "America/New_York"),
    "BWI": Airport("BWI", "Baltimore", 39.1754, -76.6683, "America/New_York"),
    "SLC": Airport("SLC", "Salt Lake City", 40.7889, -111.9799, "America/Denver"),
    "SAN": Airport("SAN", "San Diego", 32.7336, -117.1900, "America/Los_Angeles"),
    "IAD": Airport("IAD", "Washington Dulles", 38.9445, -77.4558, "America/New_York"),
    "STL": Airport("STL", "St. Louis", 38.7487, -90.3700, "America/Chicago"),
    "MCI": Airport("MCI", "Kansas City", 39.3017, -94.7139, "America/Chicago"),
    "CVG": Airport("CVG", "Cincinnati", 39.0488, -84.6678, "America/New_York"),
    "IND": Airport("IND", "Indianapolis", 39.7173, -86.2944, "America/Indiana/Indianapolis"),
    "CLE": Airport("CLE", "Cleveland", 41.4117, -81.8498, "America/New_York"),
    "PIT": Airport("PIT", "Pittsburgh", 40.4915, -80.2329, "America/New_York"),
    "MKE": Airport("MKE", "Milwaukee", 42.9472, -87.8966, "America/Chicago"),
    "RDU": Airport("RDU", "Raleigh-Durham", 35.8787, -78.7873, "America/New_York"),
    "AUS": Airport("AUS", "Austin", 30.1975, -97.6620, "America/Chicago"),
    "SAT": Airport("SAT", "San Antonio", 29.5337, -98.4698, "America/Chicago"),
    "MDW": Airport("MDW", "Chicago Midway", 41.7860, -87.7524, "America/Chicago"),
    "TPA": Airport("TPA", "Tampa", 27.9755, -82.5332, "America/New_York"),
    "MCO": Airport("MCO", "Orlando", 28.4294, -81.3090, "America/New_York"),
    "FLL": Airport("FLL", "Fort Lauderdale", 26.0726, -80.1527, "America/New_York"),
    "DCA": Airport("DCA", "Washington Reagan", 38.8521, -77.0377, "America/New_York"),
    "EWR": Airport("EWR", "Newark", 40.6894, -74.1705, "America/New_York"),
    "HNL": Airport("HNL", "Honolulu", 21.3184, -157.9257, "Pacific/Honolulu"),
    "PDX": Airport("PDX", "Portland", 45.5887, -122.5980, "America/Los_Angeles"),
    "SMF": Airport("SMF", "Sacramento", 38.6954, -121.5910, "America/Los_Angeles"),
    "OAK": Airport("OAK", "Oakland", 37.7201, -122.2212, "America/Los_Angeles"),
    "SJC": Airport("SJC", "San Jose", 37.3625, -121.9292, "America/Los_Angeles"),
    "BNA": Airport("BNA", "Nashville", 36.1245, -86.6782, "America/Chicago"),
    "MSY": Airport("MSY", "New Orleans", 29.9934, -90.2647, "America/Chicago"),
    "HND": Airport("HND", "Tokyo Haneda", 35.5497, 139.7870, "Asia/Tokyo"),
    "NRT": Airport("NRT", "Tokyo Narita", 35.7686, 140.3887, "Asia/Tokyo"),
    "KIX": Airport("KIX", "Osaka Kansai", 34.4273, 135.2440, "Asia/Tokyo"),
    "PVG": Airport("PVG", "Shanghai Pudong", 31.1434, 121.8050, "Asia/Shanghai"),
    "LHR": Airport("LHR", "London Heathrow", 51.4707, -0.4599, "Europe/London"),
    "CDG": Airport("CDG", "Paris Charles de Gaulle", 49.0090, 2.5541, "Europe/Paris"),
    "FRA": Airport("FRA", "Frankfurt", 50.0267, 8.5584, "Europe/Berlin"),
    "AMS": Airport("AMS", "Amsterdam Schiphol", 52.3086, 4.7639, "Europe/Amsterdam"),
    "DXB": Airport("DXB", "Dubai", 25.2498, 55.3710, "Asia/Dubai"),
    "SIN": Airport("SIN", "Singapore Changi", 1.3502, 103.9940, "Asia/Singapore"),
    "ICN": Airport("ICN", "Seoul Incheon", 37.4691, 126.4510, "Asia/Seoul"),
    "SYD": Airport("SYD", "Sydney", -33.9461, 151.1770, "Australia/Sydney"),
    "YYZ": Airport("YYZ", "Toronto Pearson", 43.6759, -79.6294, "America/Toronto"),
}
