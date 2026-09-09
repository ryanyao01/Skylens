"""Combines live traffic, weather and the quantile models into airport scores."""

from __future__ import annotations

import json
import pickle
from datetime import UTC, datetime

import numpy as np

from skylens.config import settings
from skylens.logging_config import get_logger
from skylens.pipeline.cascade import load_propagation, run_all_cascades
from skylens.pipeline.opensky import (
    extract_count,
    fetch_all_airport_counts,
    update_peak_observations,
)
from skylens.pipeline.weather import fetch_all_weather

logger = get_logger(__name__)

QUANTILES = ("q10", "q50", "q90")


def load_label_encoder() -> dict[str, int]:
    """Load the airport -> integer mapping used as a model feature.

    Stored as JSON rather than a pickled ``sklearn.LabelEncoder``. The encoder
    was only ever a sorted-class lookup, so a plain dict reproduces it exactly
    while removing scikit-learn (and scipy) from the runtime dependency set and
    avoiding version-skew warnings when unpickling across sklearn releases.

    Regenerate with ``python scripts/export_label_encoder.py`` after retraining.
    """
    with open(settings.label_encoder_file, encoding="utf-8") as f:
        return json.load(f)


def load_models() -> dict:
    models: dict = {}
    for q in QUANTILES:
        path = settings.models_path / f"xgb_{q}.pkl"
        with open(path, "rb") as f:
            models[q] = pickle.load(f)
    models["le"] = load_label_encoder()
    logger.info(
        "models loaded",
        extra={"quantiles": list(QUANTILES), "encoder_classes": len(models["le"])},
    )
    return models


def load_airport_profile() -> dict:
    with open(settings.airport_profile_file, encoding="utf-8") as f:
        return json.load(f)


def slot_key(airport: str, dow: int, hour: int) -> str:
    return f"{airport}|{dow}|{hour}"


def get_hist_mean(profile: dict, airport: str, dow: int, hour: int) -> float:
    key = slot_key(airport, dow, hour)
    if key in profile.get("hist_mean_by_slot", {}):
        return float(profile["hist_mean_by_slot"][key])
    if airport in profile.get("hist_mean_default", {}):
        return float(profile["hist_mean_default"][airport])
    return float(profile["fallback_airports"][airport]["hist_mean_arrivals"])


def airport_codes(profile: dict) -> list[str]:
    trained = profile.get("trained_airports", [])
    fallback = profile.get("fallback_airports", {}).keys()
    return list(dict.fromkeys([*trained, *fallback]))


def weather_penalty(w: dict) -> float:
    """
    Returns a multiplier from 0.5 to 1.0.
    1.0 = perfect conditions, no penalty.
    0.5 = severe conditions, capacity halved.
    """
    penalty = 1.0

    wind = w.get("wind_speed_kn", 0)
    precip = w.get("precipitation_mm", 0)
    vis = w.get("visibility_m", 10000)
    gusts = w.get("wind_gusts_kn", 0)

    if wind > 30 or gusts > 40:
        penalty -= 0.25
    elif wind > 20 or gusts > 30:
        penalty -= 0.15
    elif wind > 15:
        penalty -= 0.05

    if precip > 5:
        penalty -= 0.25
    elif precip > 1:
        penalty -= 0.15
    elif precip > 0:
        penalty -= 0.05

    if vis < 3000:
        penalty -= 0.25
    elif vis < 8000:
        penalty -= 0.10
    elif vis < 15000:
        penalty -= 0.05

    return max(penalty, 0.5)


def compute_scores(
    models: dict,
    flight_counts: dict,
    weather: dict,
    peak_observations: dict | None = None,
) -> dict:
    if peak_observations is None:
        peak_observations = {}

    profile = load_airport_profile()
    now = datetime.now(UTC)
    hour = now.hour
    minute = now.minute
    block = minute // 15
    dow = now.weekday() + 1
    month = now.month
    is_weekend = 1 if dow >= 6 else 0

    scores = {}
    trained_airports = set(profile.get("trained_airports", []))
    encoder_airports = set(models["le"])

    for airport in airport_codes(profile):
        hist_mean = get_hist_mean(profile, airport, dow, hour)
        is_model_trained = airport in trained_airports and airport in encoder_airports

        if is_model_trained:
            airport_enc = models["le"][airport]
            features = np.array([[
                hour,
                block,
                dow,
                month,
                is_weekend,
                hist_mean,
                airport_enc,
            ]])
            pred_q50 = max(models["q50"].predict(features)[0], 0.5)
        else:
            pred_q50 = max(hist_mean, 0.5)

        w = weather.get(airport, {})
        penalty = weather_penalty(w)
        adjusted_capacity = pred_q50 * penalty

        # OpenSky count is live aircraft density, not arrivals per 15-minute slot.
        live_count = extract_count(flight_counts.get(airport, 0))
        live_metadata = flight_counts.get("_metadata", {}).get(airport, {})
        baseline_peak = profile["live_peak_counts"].get(airport, 50)
        observed_peak = peak_observations.get(airport, {}).get("peak", 0)
        peak_count = max(baseline_peak, observed_peak)
        peak_source = "observed" if observed_peak > baseline_peak else "baseline"
        effective_peak = peak_count * penalty
        raw_score = (live_count / effective_peak) * 100
        score = min(round(raw_score, 1), 100)

        fallback_info = profile.get("fallback_airports", {}).get(airport)
        offline_peak = (
            fallback_info["peak_capacity"]
            if fallback_info
            else profile["peak_capacity"][airport]
        )

        scores[airport] = {
            "score": float(score),
            "live_flights": int(live_count),
            "pred_capacity": float(round(adjusted_capacity, 2)),
            "hist_mean_arrivals": float(round(hist_mean, 2)),
            "offline_peak_capacity": float(round(offline_peak, 2)),
            "live_peak_count": int(peak_count),
            "peak_source": peak_source,
            "weather_penalty": float(round(penalty, 2)),
            "wind_kn": float(w.get("wind_speed_kn", 0)),
            "precip_mm": float(w.get("precipitation_mm", 0)),
            "visibility_m": float(w.get("visibility_m", 10000)),
            "model_trained": bool(is_model_trained),
            "scoring_basis": "opensky_density_vs_live_peak_count",
            "live_data_status": live_metadata.get("status", "unknown"),
            "live_data_message": live_metadata.get("message", ""),
            "timestamp": now.isoformat(),
        }
        if fallback_info:
            scores[airport]["fallback_note"] = fallback_info["note"]

    return scores




def main() -> None:
    """Run one scoring pass offline and write the snapshot files.

    Note this writes ``live_scores.json`` without coordinates; the API merges
    those in at request time. The file is a debugging snapshot, not the source
    the API serves from.
    """
    from skylens.logging_config import configure_logging

    configure_logging()

    logger.info("loading models...")
    models = load_models()

    logger.info("fetching live data...")
    flight_counts = fetch_all_airport_counts()
    peak_observations = update_peak_observations(flight_counts)
    weather = fetch_all_weather()

    logger.info("computing scores...")
    scores = compute_scores(models, flight_counts, weather, peak_observations)

    print("\n--- live imbalance scores ---")
    for airport, data in sorted(
        scores.items(),
        key=lambda x: x[1]["score"],
        reverse=True,
    ):
        bar = "#" * int(data["score"] / 5)
        print(f"{airport}  {data['score']:5.1f}  {bar}")
        print(
            f"       flights={data['live_flights']} "
            f"source={data['live_data_status']} "
            f"capacity={data['pred_capacity']} "
            f"weather={data['weather_penalty']} "
            f"wind={data['wind_kn']}kn"
        )

    settings.state_path.mkdir(parents=True, exist_ok=True)
    with open(settings.live_scores_file, "w", encoding="utf-8") as f:
        json.dump(scores, f, indent=2)
    logger.info("scores saved", extra={"path": str(settings.live_scores_file)})

    propagation = load_propagation()
    all_cascades = run_all_cascades(scores, propagation)
    with open(settings.cascade_forecast_file, "w", encoding="utf-8") as f:
        json.dump(all_cascades, f, indent=2)
    logger.info(
        "cascade saved",
        extra={
            "triggering_airports": len(all_cascades),
            "path": str(settings.cascade_forecast_file),
        },
    )


if __name__ == "__main__":
    main()
