"""Open-Meteo client: current conditions at each tracked airport."""

from __future__ import annotations

from datetime import UTC, datetime

import requests

from skylens.airports import AIRPORTS
from skylens.config import settings
from skylens.logging_config import get_logger

logger = get_logger(__name__)

# Open-Meteo free API - no key needed
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# Derived from the single airport table rather than maintained separately.
AIRPORT_COORDS = {code: (a.lat, a.lon) for code, a in AIRPORTS.items()}

CURRENT_FIELDS = (
    "wind_speed_10m",
    "wind_gusts_10m",
    "precipitation",
    "cloud_cover",
    "visibility",
    "weather_code",
)


def _parse_current(airport_code: str, current: dict) -> dict:
    return {
        "airport": airport_code,
        "wind_speed_kn": current.get("wind_speed_10m", 0),
        "wind_gusts_kn": current.get("wind_gusts_10m", 0),
        "precipitation_mm": current.get("precipitation", 0),
        "cloud_cover_pct": current.get("cloud_cover", 0),
        "visibility_m": current.get("visibility", 10000),
        "weather_code": current.get("weather_code", 0),
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _request(codes: list[str]) -> requests.Response:
    return requests.get(
        WEATHER_URL,
        params={
            "latitude": ",".join(str(AIRPORT_COORDS[c][0]) for c in codes),
            "longitude": ",".join(str(AIRPORT_COORDS[c][1]) for c in codes),
            "current": ",".join(CURRENT_FIELDS),
            "wind_speed_unit": "kn",
            "timezone": "UTC",
        },
        timeout=max(settings.http_timeout_seconds, 20),
    )


def fetch_weather(airport_code: str) -> dict:
    """Current conditions for one airport. Returns {} on failure."""
    try:
        response = _request([airport_code])
        if response.status_code == 200:
            return _parse_current(airport_code, response.json()["current"])
        logger.warning(
            "weather request failed",
            extra={"airport": airport_code, "status_code": response.status_code},
        )
    except Exception as e:
        logger.warning("weather request errored", extra={"airport": airport_code, "error": str(e)})
    return {}


def fetch_all_weather() -> dict:
    """Current conditions for every airport, in one request.

    Open-Meteo accepts comma-separated coordinate lists and answers with one
    result per location, in order -- one round trip instead of 58. If the batch
    fails, every airport gets {}, which the scorer treats as "no penalty" rather
    than as bad weather.
    """
    codes = list(AIRPORT_COORDS)
    try:
        response = _request(codes)
        if response.status_code == 200:
            payload = response.json()
            results = payload if isinstance(payload, list) else [payload]
            if len(results) == len(codes):
                weather = {
                    code: _parse_current(code, result.get("current") or {})
                    for code, result in zip(codes, results, strict=True)
                }
                logger.info("weather sweep complete", extra={"airports": len(codes), "missing": 0})
                return weather
            logger.warning(
                "weather batch returned the wrong number of locations",
                extra={"expected": len(codes), "received": len(results)},
            )
        else:
            logger.warning("weather batch failed", extra={"status_code": response.status_code})
    except Exception as e:
        logger.warning("weather batch errored", extra={"error": str(e)})

    logger.info("weather sweep complete", extra={"airports": len(codes), "missing": len(codes)})
    return {code: {} for code in codes}


if __name__ == "__main__":
    from skylens.logging_config import configure_logging

    configure_logging()
    for airport, w in fetch_all_weather().items():
        logger.info(
            "%s: wind=%skn precip=%smm cloud=%s%% vis=%sm",
            airport,
            w.get("wind_speed_kn"),
            w.get("precipitation_mm"),
            w.get("cloud_cover_pct"),
            w.get("visibility_m"),
        )
