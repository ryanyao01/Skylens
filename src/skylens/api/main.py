"""SkyLens HTTP API.

Every refresh runs one pipeline: fetch -> score -> cascade -> data-quality
checks -> persist to the warehouse. Live endpoints read an in-memory cache;
history and analytics endpoints read the warehouse. No request ever blocks on
an upstream API.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from importlib import resources
from uuid import uuid4

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from skylens import __version__, quality
from skylens.airports import AIRPORTS
from skylens.config import settings
from skylens.logging_config import configure_logging, get_logger
from skylens.pipeline.cascade import load_propagation, run_all_cascades
from skylens.pipeline.opensky import fetch_all_airport_counts, update_peak_observations
from skylens.pipeline.scorer import compute_scores, load_airport_profile, load_models
from skylens.pipeline.weather import fetch_all_weather
from skylens.warehouse import Warehouse, close_warehouse, get_warehouse, open_warehouse

# Configured at import time, not just in lifespan: uvicorn installs its own
# logging during startup and emits its first lines before the lifespan hook
# runs, so configuring here keeps the whole stream in one format.
configure_logging()

logger = get_logger(__name__)

# Display fields merged into each airport's score, derived from the single
# airport table rather than kept as a second copy.
AIRPORT_COORDS = {
    code: {"lat": a.lat, "lon": a.lon, "name": a.name} for code, a in AIRPORTS.items()
}

# The backtest reports no verdict until this many predictions have matured.
MIN_MATURED_PREDICTIONS = 30

# in-memory state served by the live endpoints
score_cache: dict = {}
cascade_cache: dict = {}
last_refresh_at: str | None = None
last_refresh_error: str | None = None
last_quality: dict | None = None
models: dict | None = None
scheduler: BackgroundScheduler | None = None


def _persist(run_id: str, started: datetime, finished: datetime, counts: dict,
             weather: dict, scores: dict, cascade: dict, checks: list[dict]) -> None:
    """Write the run to the warehouse. Never allowed to break live serving."""
    warehouse = get_warehouse()
    if warehouse is None:
        return
    try:
        warehouse.record_run(
            run_id=run_id, started_at=started, finished_at=finished,
            flight_counts=counts, weather=weather, scores=scores, cascade=cascade,
            error=None if counts.get("_run", {}).get("status") == "ok"
            else counts.get("_run", {}).get("status"),
        )
        warehouse.record_quality(run_id, finished, checks)
    except Exception:
        logger.exception("warehouse write failed", extra={"run_id": run_id})


def refresh_scores() -> None:
    global score_cache, cascade_cache, last_refresh_at, last_refresh_error, last_quality

    run_id = uuid4().hex
    started = datetime.now(UTC)
    try:
        flight_counts = fetch_all_airport_counts()
        peak_observations = update_peak_observations(flight_counts)
        weather = fetch_all_weather()
        scores = compute_scores(models, flight_counts, weather, peak_observations, now=started)
        for icao, data in scores.items():
            scores[icao] = {**data, **AIRPORT_COORDS.get(icao, {})}
        cascade = run_all_cascades(scores, load_propagation())
    except Exception as e:
        last_refresh_error = str(e)
        logger.exception("score refresh failed", extra={"run_id": run_id})
        return

    warehouse = get_warehouse()
    previous_total = None
    if warehouse is not None:
        try:
            previous_total = warehouse.previous_run_aircraft_total()
        except Exception:
            logger.exception("could not read previous run from the warehouse")

    finished = datetime.now(UTC)
    checks = quality.run_checks(
        flight_counts=flight_counts, weather=weather, scores=scores,
        now=finished, previous_aircraft_total=previous_total,
    )
    verdict = quality.summarize(checks)

    upstream = flight_counts.get("_run", {}).get("status")
    if upstream == "ok":
        score_cache = scores
        cascade_cache = cascade
        last_refresh_at = finished.isoformat()
        last_refresh_error = None
    else:
        # A failed upstream request scores every airport 0. Serving that would
        # paint the whole map "quiet", so keep the last good scores (each one
        # carries its own timestamp) and say so in /health.
        last_refresh_error = (
            f"upstream status {upstream!r}; serving scores from {last_refresh_at or 'never'}"
        )

    _persist(run_id, started, finished, flight_counts, weather, scores, cascade, checks)

    # Published last, so anyone who sees this run's quality verdict can also
    # find the run itself in the warehouse.
    last_quality = {
        "status": verdict,
        "run_id": run_id,
        "checked_at": finished.isoformat(),
        "failed": [c["check_name"] for c in checks if not c["passed"]],
    }

    if settings.write_runtime_json and upstream == "ok":
        settings.state_path.mkdir(parents=True, exist_ok=True)
        with open(settings.cascade_forecast_file, "w", encoding="utf-8") as f:
            json.dump(cascade_cache, f, indent=2)

    logger.info(
        "refresh complete",
        extra={
            "run_id": run_id,
            "upstream": upstream,
            "airports": len(scores),
            "cascade_triggers": len(cascade),
            "data_quality": verdict,
            "duration_s": round((finished - started).total_seconds(), 2),
        },
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Open the warehouse, load models, run the scheduler for the process's life."""
    global models, scheduler

    logger.info(
        "starting SkyLens API",
        extra={
            "version": __version__,
            "refresh_interval_s": settings.refresh_interval_seconds,
            "models_path": str(settings.models_path),
            "state_path": str(settings.state_path),
            "warehouse_enabled": settings.warehouse_enabled,
        },
    )
    settings.state_path.mkdir(parents=True, exist_ok=True)

    if settings.warehouse_enabled:
        try:
            trained = set(load_airport_profile().get("trained_airports", []))
            open_warehouse(settings.warehouse_file, trained)
        except Exception:
            # Live scoring still works without history; say so loudly.
            logger.exception("warehouse unavailable; continuing without history")

    models = load_models()
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        refresh_scores,
        "interval",
        seconds=settings.refresh_interval_seconds,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(UTC),
    )
    scheduler.start()

    yield

    logger.info("shutting down SkyLens API")
    if scheduler:
        scheduler.shutdown(wait=False)
    close_warehouse()


app = FastAPI(title="SkyLens API", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_warehouse() -> Warehouse:
    warehouse = get_warehouse()
    if warehouse is None:
        raise HTTPException(status_code=503, detail="warehouse disabled or unavailable")
    return warehouse


def _known_airport(icao: str) -> str:
    code = icao.upper()
    if code not in AIRPORTS:
        raise HTTPException(status_code=404, detail=f"airport {icao} not found")
    return code


# ------------------------------------------------------------------ dashboard
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    return (resources.files("skylens") / "web" / "index.html").read_text(encoding="utf-8")


# ----------------------------------------------------------------------- live
@app.get("/airports/scores")
def get_scores():
    if score_cache:
        return score_cache
    raise HTTPException(status_code=503, detail="scores not yet computed")


@app.get("/airports/{icao}/score")
def get_airport_score(icao: str):
    if icao.upper() in score_cache:
        return score_cache[icao.upper()]
    raise HTTPException(status_code=404, detail=f"airport {icao} not found")


@app.get("/forecast/cascade")
def get_cascade():
    if cascade_cache:
        return cascade_cache
    raise HTTPException(status_code=503, detail="cascade forecast not yet computed")


@app.get("/forecast/cascade/{icao}")
def get_airport_cascade(icao: str):
    if icao.upper() in cascade_cache:
        return cascade_cache[icao.upper()]
    raise HTTPException(status_code=404, detail=f"no cascade data for {icao}")


@app.get("/health")
def health():
    warehouse = get_warehouse()
    return {
        "status": "ok" if score_cache and not last_refresh_error else "degraded",
        "airports_cached": len(score_cache),
        "cascade_airports_cached": len(cascade_cache),
        "last_refresh_at": last_refresh_at,
        "last_refresh_error": last_refresh_error,
        "refresh_interval_seconds": settings.refresh_interval_seconds,
        "data_quality": last_quality,
        "warehouse": {
            "enabled": settings.warehouse_enabled,
            "available": warehouse is not None,
            "runs_recorded": warehouse.scalar("SELECT count(*) FROM ingestion_runs")
            if warehouse is not None else None,
        },
    }


# ------------------------------------------------------------------- pipeline
@app.get("/quality")
def data_quality():
    warehouse = _require_warehouse()
    return {
        "latest": last_quality,
        "checks": warehouse.query(
            "SELECT * FROM mart_data_quality ORDER BY severity, check_name"
        ),
    }


@app.get("/pipeline/runs")
def pipeline_runs(limit: int = Query(20, ge=1, le=500)):
    return _require_warehouse().query(
        "SELECT * FROM ingestion_runs ORDER BY started_at DESC LIMIT ?", [limit]
    )


@app.get("/pipeline/daily")
def pipeline_daily():
    return _require_warehouse().query("SELECT * FROM mart_pipeline_health ORDER BY day_utc DESC")


# ------------------------------------------------------------------ analytics
@app.get("/analytics/leaderboard")
def leaderboard(limit: int = Query(15, ge=1, le=58)):
    return _require_warehouse().query(
        "SELECT * FROM mart_airport_leaderboard "
        "ORDER BY pct_time_stressed DESC, avg_score DESC LIMIT ?",
        [limit],
    )


@app.get("/analytics/hourly/{icao}")
def hourly_profile(icao: str):
    code = _known_airport(icao)
    return _require_warehouse().query(
        "SELECT * FROM mart_airport_hourly WHERE airport = ? ORDER BY local_hour", [code]
    )


@app.get("/analytics/history/{icao}")
def score_history(icao: str, hours: int = Query(24, ge=1, le=24 * 30)):
    code = _known_airport(icao)
    since = (datetime.now(UTC) - timedelta(hours=hours)).replace(tzinfo=None)
    return _require_warehouse().query(
        "SELECT observed_at, score, projected_score, live_flights, local_hour "
        "FROM stg_scores WHERE airport = ? AND observed_at >= ? ORDER BY observed_at",
        [code, since],
    )


@app.get("/analytics/cascade-backtest")
def cascade_backtest():
    rows = _require_warehouse().query("SELECT * FROM mart_cascade_backtest")
    matured = sum(r["n_predicted"] or 0 for r in rows)

    if matured < MIN_MATURED_PREDICTIONS:
        verdict = "insufficient_data"
        summary = (
            f"{matured} matured predictions so far; at least {MIN_MATURED_PREDICTIONS} are "
            "needed. A prediction matures 1-6 hours after the cascade fires."
        )
    else:
        supported = [r["horizon_h"] for r in rows if (r["welch_t"] or 0) >= 2 and r["lift"] > 0]
        contradicted = [r["horizon_h"] for r in rows if (r["welch_t"] or 0) <= -2]
        if supported:
            verdict = "supported"
            summary = f"Named airports rose more than controls at horizon(s) {supported} h."
        elif contradicted:
            verdict = "contradicted"
            summary = f"Named airports rose LESS than controls at horizon(s) {contradicted} h."
        else:
            verdict = "no_evidence_yet"
            summary = "No horizon shows a difference distinguishable from noise (|t| < 2)."

    return {
        "verdict": verdict,
        "summary": summary,
        "matured_predictions": matured,
        "by_horizon": rows,
        "method": (
            "For every run where the cascade fired, compare the score change of airports it "
            "named against airports it did not name over the same window. Positive lift with "
            "|Welch t| >= 2 counts as evidence."
        ),
    }
