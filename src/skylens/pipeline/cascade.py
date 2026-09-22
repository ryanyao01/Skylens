"""Delay-cascade simulation over the learned route propagation graph."""

from __future__ import annotations

import pickle

from skylens.config import settings

CASCADE_THRESHOLD = 65.0


def load_propagation() -> dict:
    """Load the airport -> {downstream: probability} propagation map.

    The artifact is a plain nested dict, so this needs no third-party library
    at import time.
    """
    with open(settings.models_path / "propagation.pkl", "rb") as f:
        return pickle.load(f)


def simulate_cascade(
    stressed_airport: str,
    current_scores: dict,
    propagation: dict,
    threshold: float = CASCADE_THRESHOLD,
    hours_ahead: int = 6,
    decay: float = 0.6
) -> dict:
    results = {h: {} for h in range(1, hours_ahead + 1)}

    trigger_score = current_scores.get(stressed_airport, {})
    if isinstance(trigger_score, dict):
        trigger_score = trigger_score.get("score", 0)

    if trigger_score < threshold:
        return results

    initial_impact = max(
        (trigger_score - threshold) / (100 - threshold),
        0.1
    )

    visited = {stressed_airport: initial_impact}
    current_wave = {stressed_airport: initial_impact}

    for hour in range(1, hours_ahead + 1):
        next_wave = {}

        for airport, impact in current_wave.items():
            if airport not in propagation:
                continue

            for downstream, prob in propagation[airport].items():
                if downstream in visited:
                    continue

                downstream_impact = impact * prob * decay * 20

                if downstream_impact > 0.01:
                    if downstream not in next_wave:
                        next_wave[downstream] = 0
                    next_wave[downstream] += downstream_impact
                    visited[downstream] = downstream_impact

        results[hour] = {
            airport: round(min(impact * 100, 50.0), 1)
            for airport, impact in next_wave.items()
        }
        current_wave = next_wave

    return results


def run_all_cascades(scores: dict, propagation: dict) -> dict:
    all_cascades = {}
    for airport, data in scores.items():
        score = data["score"] if isinstance(data, dict) else 0
        if score >= CASCADE_THRESHOLD:
            cascade = simulate_cascade(airport, scores, propagation)
            all_cascades[airport] = cascade
    return all_cascades