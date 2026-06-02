from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import os

app = FastAPI(title="SkyLens API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

@app.get("/airports/scores")
def get_scores():
    scores_path = PROJECT_ROOT / "data" / "clean" / "live_scores.json"
    if scores_path.exists():
        with open(scores_path) as f:
            return json.load(f)
    return {"error": "scores not yet computed"}

@app.get("/airports/{icao}/score")
def get_airport_score(icao: str):
    scores_path = PROJECT_ROOT / "data" / "clean" / "live_scores.json"
    if scores_path.exists():
        with open(scores_path) as f:
            scores = json.load(f)
        if icao.upper() in scores:
            return scores[icao.upper()]
    return {"error": f"airport {icao} not found"}

@app.get("/health")
def health():
    return {"status": "ok"}