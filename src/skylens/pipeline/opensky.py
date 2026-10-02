"""OpenSky Network client: live aircraft counts per airport bounding box."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import UTC, datetime, timedelta

import requests

from skylens.config import settings
from skylens.logging_config import get_logger

logger = get_logger(__name__)

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
TOKEN_REFRESH_MARGIN = 30  # seconds before expiration to refresh the token


class TokenManager:
    """Caches an OAuth client-credentials token and refreshes it before expiry.

    Guarded by a lock because the API refreshes scores on a background
    scheduler thread while requests are served on others.
    """

    def __init__(self) -> None:
        self.token: str | None = None
        self.expires_at: datetime | None = None
        self._lock = threading.Lock()

    def get_token(self) -> str:
        with self._lock:
            if (
                self.token
                and self.expires_at
                and datetime.now(UTC) < self.expires_at
            ):
                return self.token
            return self._refresh()

    def _refresh(self) -> str:
        if not settings.opensky_client_id or not settings.opensky_client_secret:
            raise RuntimeError(
                "OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET must be set to reach OpenSky"
            )
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.opensky_client_id,
                "client_secret": settings.opensky_client_secret,
            },
            timeout=settings.http_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        self.token = data["access_token"]
        expires_in = data.get("expires_in", 1800)
        self.expires_at = datetime.now(UTC) + timedelta(
            seconds=expires_in - TOKEN_REFRESH_MARGIN
        )
        logger.info("opensky token refreshed", extra={"expires_in_s": expires_in})
        return self.token

    def invalidate(self) -> None:
        """Drop the cached token so the next request fetches a fresh one."""
        with self._lock:
            self.token = None
            self.expires_at = None

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.get_token()}"}


tokens = TokenManager()

# Serializes the read-modify-write of the peak-observations file. This is a
# stopgap: the file is process-local, so it does not protect against a second
# worker. Moving this state into a database removes the constraint.
_observations_lock = threading.Lock()


def load_peak_observations() -> dict:
    try:
        with open(settings.peak_observations_file, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        logger.warning(
            "peak observations file is corrupt; starting from empty",
            extra={"path": str(settings.peak_observations_file)},
        )
        return {}


def _write_peak_observations(observations: dict) -> None:
    """Write atomically so a crash mid-write cannot truncate the file."""
    path = settings.peak_observations_file
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(observations, f, indent=2)
    os.replace(tmp, path)


def update_peak_observations(counts: dict) -> dict:
    with _observations_lock:
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
        _write_peak_observations(observations)
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


NO_STATES_MESSAGE = (
    "OpenSky returned no aircraft inside this bounding box; this can mean true "
    "inactivity or incomplete receiver coverage."
)

# One worldwide request is ~1.6 MB and takes a few seconds, so it gets more
# headroom than the per-airport timeout.
GLOBAL_TIMEOUT_S = 30
MAX_ATTEMPTS = 3


def _credits(response: requests.Response) -> int | None:
    value = response.headers.get("X-Rate-Limit-Remaining")
    return int(value) if value and value.lstrip("-").isdigit() else None


def fetch_global_states() -> tuple[list | None, dict]:
    """Fetch every aircraft OpenSky can see, in a single request.

    Why one global call instead of one per airport: OpenSky meters usage in
    credits, 4,000 a day. A bounding-box query costs 1 credit, so 58 airports
    every 15 minutes is 5,568 credits a day -- the quota ran out after about 17
    hours and every airport silently went to zero until midnight UTC. A
    worldwide query costs 4 credits and returns the same aircraft; the boxes are
    applied locally. 384 credits a day, and ~2 seconds instead of ~80.

    Returns ``(states, info)``. ``states`` is None when the request failed, and
    ``info["status"]`` says why.
    """
    info: dict = {"attempts": 0, "credits_remaining": None}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        info["attempts"] = attempt
        try:
            response = requests.get(
                OPENSKY_URL, headers=tokens.headers(), timeout=GLOBAL_TIMEOUT_S
            )
        except RuntimeError as e:  # credentials missing: retrying cannot help
            info.update(status="config_error", message=str(e))
            return None, info
        except requests.RequestException as e:
            info.update(status="network_error", message=str(e))
        else:
            info["credits_remaining"] = _credits(response)
            if response.status_code == 200:
                data = response.json()
                info.update(status="ok", api_time=data.get("time"))
                return data.get("states") or [], info
            if response.status_code == 429:
                # The daily quota is spent; retrying now cannot succeed.
                wait = response.headers.get("X-Rate-Limit-Retry-After-Seconds")
                info.update(
                    status="rate_limited",
                    message=f"OpenSky daily quota exhausted; resets in {wait}s",
                )
                return None, info
            if response.status_code == 401:
                tokens.invalidate()  # token rejected early: fetch a new one and retry
            info.update(
                status="api_error",
                message=f"OpenSky returned HTTP {response.status_code}",
            )
            if 400 <= response.status_code < 500 and response.status_code != 401:
                return None, info  # a client error will fail identically again
        if attempt < MAX_ATTEMPTS:
            delay = 2**attempt
            logger.warning(
                "opensky request failed, retrying",
                extra={"attempt": attempt, "retry_in_s": delay, "status": info.get("status")},
            )
            time.sleep(delay)
    return None, info


def count_aircraft_in_boxes(states: list) -> dict[str, int]:
    """Count aircraft inside each airport's bounding box.

    Boxes can overlap (JFK/LGA/EWR, ORD/MDW), so one aircraft may count toward
    several airports -- the same result separate bounding-box queries gave.
    """
    counts = dict.fromkeys(AIRPORT_BOUNDS, 0)
    boxes = list(AIRPORT_BOUNDS.items())
    for state in states:
        lon, lat = state[5], state[6]  # OpenSky state vector: index 5 lon, 6 lat
        if lon is None or lat is None:
            continue
        for code, (lat_min, lat_max, lon_min, lon_max) in boxes:
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                counts[code] += 1
    return counts


def fetch_all_airport_counts() -> dict:
    """Aircraft count and data status for every tracked airport.

    Returns ``{code: count, ..., "timestamp": iso, "_metadata": {code: {...}},
    "_run": {...}}``. ``_run`` describes the upstream request itself (credits
    left, attempts, aircraft seen worldwide) and feeds the data-quality checks.
    """
    started = time.monotonic()
    states, info = fetch_global_states()

    counts: dict = {}
    metadata: dict = {}
    if states is None:
        for code in AIRPORT_BOUNDS:
            counts[code] = 0
            metadata[code] = {"status": info["status"], "message": info.get("message", "")}
    else:
        for code, n in count_aircraft_in_boxes(states).items():
            counts[code] = n
            metadata[code] = {
                "status": "ok" if n > 0 else "no_states",
                "message": "Aircraft found inside the bounding box." if n > 0 else NO_STATES_MESSAGE,
                "api_time": info.get("api_time"),
            }

    counts["timestamp"] = datetime.now(UTC).isoformat()
    counts["_metadata"] = metadata
    counts["_run"] = {
        "source": "opensky_global",
        "status": info["status"],
        "attempts": info["attempts"],
        "credits_remaining": info["credits_remaining"],
        "aircraft_worldwide": len(states) if states is not None else None,
        "elapsed_s": round(time.monotonic() - started, 2),
    }

    degraded = sum(1 for m in metadata.values() if m["status"] != "ok")
    logger.info(
        "opensky sweep complete",
        extra={**counts["_run"], "airports": len(AIRPORT_BOUNDS), "degraded": degraded},
    )
    return counts


if __name__ == "__main__":
    from skylens.logging_config import configure_logging

    configure_logging()
    result = fetch_all_airport_counts()
    logger.info("run: %s", result["_run"])
    for code in AIRPORT_BOUNDS:
        logger.info("%s: %s (%s)", code, result[code], result["_metadata"][code]["status"])
