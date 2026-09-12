# SkyLens

[![CI](https://github.com/ryanyao01/Skylens/actions/workflows/ci.yml/badge.svg)](https://github.com/ryanyao01/Skylens/actions/workflows/ci.yml)

Real-time airport congestion scoring and delay-cascade forecasting for 58 airports
worldwide, with a React Native client that renders them on a live map.

SkyLens answers two questions: **how busy is this airport right now, relative to
what it can handle**, and **if it is overloaded, which airports get hit next**.

---

## How it works

```
OpenSky Network  ──┐
(aircraft density  │
 per bounding box) │
                   ├──►  scorer  ──►  in-memory cache  ──►  FastAPI  ──►  Expo app
Open-Meteo       ──┤     │                  ▲                             (globe map)
(wind/precip/vis)  │     │                  │
                   │     ├─ XGBoost q10/q50/q90 (demand forecast)
airport profile  ──┘     └─ propagation graph  ──►  cascade simulation
(trained offline)
```

A background scheduler recomputes every airport every 15 minutes. Requests always
read the cache, so no client request ever blocks on an upstream API.

### The congestion score

```
score = live_aircraft / (peak_density × weather_penalty) × 100      capped at 100
```

- **`live_aircraft`** — aircraft inside the airport's bounding box, from OpenSky.
  This is a *density* snapshot, not an arrival count.
- **`peak_density`** — that airport's busiest observed density. Seeded from the
  trained model (see below) and raised whenever a higher live value is observed.
- **`weather_penalty`** — 0.5 to 1.0, from wind, gusts, precipitation and
  visibility. Bad weather shrinks effective capacity, so the same traffic scores
  higher.

A score of 100 means the airport is at or above its known peak. The cascade
simulation treats **≥ 65** as stressed.

### The delay cascade

When an airport crosses 65, a learned route-propagation graph is walked
breadth-first for 6 hours with a 0.6 decay per hop, estimating downstream impact
at each step. This is the part of the system most worth looking at — it turns a
per-airport snapshot into a network-level forecast.

---

## The model, honestly

Three XGBoost quantile regressors (q10/q50/q90) predict **arrivals per 15-minute
slot** from `(hour, quarter-hour block, day of week, month, weekend flag,
historical slot mean, airport)`, trained on 43 US airports.

**Measured results** (from `notebooks/Week 2/Training.ipynb`):

| model | MAE (arrivals per 15-min slot) |
|---|---|
| baseline (historical slot mean) | 0.4670 |
| XGBoost, no airport encoding | 0.4598 |
| XGBoost, with airport encoding | **0.4581** |

That is a **1.9% improvement over the naive baseline** — real but modest. Quantile
losses: q10 0.3703, q50 0.3516, q90 0.9265.

**Where the model actually reaches the product:**

1. **Peak calibration (offline).** The models predict arrivals; OpenSky reports
   density. These are different units. Fitting `density ≈ k × model_peak_capacity`
   on 10 airports with both values measured gives **k ≈ 21.96**, which derives a
   per-airport `peak_density` for every trained airport rather than a hardcoded
   constant.
2. **Demand forecast (live).** Each refresh predicts the next hour's arrivals at
   q10/q50/q90, exposed as `forecast_next_hour` with an uncertainty band, plus a
   `demand_trend` and a `projected_score` that extrapolates current utilisation by
   the predicted change in demand.

**Known limitation:** 24 of 43 trained airports have their `peak_capacity` pinned
at a floor of 2.00 arrivals/slot upstream, so the calibration gives them
near-identical values. Re-deriving that ceiling without the floor is the highest-
value modelling work left.

---

## Quickstart

### Docker (recommended)

```bash
cp .env.example .env    # add your OpenSky credentials
docker compose up --build
```

The first scoring pass makes 58 OpenSky + 58 weather calls and takes about two
minutes. Watch for `"message": "scores refreshed"` in the logs, then:

```bash
curl http://localhost:8080/health
```

### Local

```bash
pip install -e ".[dev]"
uvicorn skylens.api.main:app --host 0.0.0.0 --port 8080 --reload
```

Interactive API docs at <http://localhost:8080/docs>.

---

## API

| Endpoint | Description |
|---|---|
| `GET /airports/scores` | Every airport's score, forecast, weather and coordinates |
| `GET /airports/{icao}/score` | One airport (case-insensitive) |
| `GET /forecast/cascade` | Delay cascades for all airports above the threshold |
| `GET /forecast/cascade/{icao}` | One airport's 6-hour cascade |
| `GET /health` | Cache counts, last refresh time, last error |

<details>
<summary>Example response</summary>

```json
{
  "ATL": {
    "score": 53.3,
    "projected_score": 61.2,
    "demand_trend": "rising",
    "expected_arrivals": 1.36,
    "forecast_next_hour": { "p10": 1.0, "p50": 1.94, "p90": 3.11 },
    "forecast_source": "model",
    "live_flights": 64,
    "live_peak_count": 120,
    "peak_source": "observed",
    "weather_penalty": 1.0,
    "live_data_status": "ok",
    "model_trained": true,
    "lat": 33.6407, "lon": -84.4277, "name": "Atlanta"
  }
}
```
</details>

Every airport carries `live_data_status`. OpenSky receiver coverage is weak over
parts of East Asia, so an airport can return zero aircraft because nothing is
flying *or* because nothing is being received — `no_states` distinguishes them.
Clients should not treat a degraded reading as a quiet airport.

---

## Configuration

All settings are environment variables; see [`.env.example`](.env.example).

| Variable | Default | Purpose |
|---|---|---|
| `OPENSKY_CLIENT_ID` / `_SECRET` | — | **Required.** OpenSky OAuth credentials |
| `SKYLENS_REFRESH_SECONDS` | `900` | Seconds between scoring passes (min 60) |
| `SKYLENS_STATE_DIR` | `data/clean` | Where runtime state is written |
| `SKYLENS_MODELS_DIR` | `models/` | Model artifacts |
| `SKYLENS_CORS_ALLOW_ORIGINS` | `*` | Comma-separated allowlist |
| `SKYLENS_LOG_FORMAT` | `text` | `text` or `json` for log aggregators |

**`SKYLENS_STATE_DIR` matters in production.** Learned peak densities are written
there and form the score denominator. On an ephemeral filesystem they reset on
every deploy, silently shifting every score. `docker-compose.yml` mounts a named
volume for exactly this reason.

---

## Layout

```
src/skylens/
  api/main.py                  FastAPI app, scheduler, in-memory cache
  pipeline/opensky.py          OAuth client, per-airport density, peak state
  pipeline/weather.py          Open-Meteo client
  pipeline/scorer.py           Score formula + quantile demand forecast
  pipeline/cascade.py          Delay propagation simulation
  config.py                    All settings and paths, from the environment
models/                        xgb_q10/q50/q90, label encoder, propagation graph
notebooks/                     EDA, feature engineering, training, cascade graph
tests/                         86 tests, no network access
```

---

## Development

```bash
pytest                  # 86 tests, ~73% coverage
ruff check src tests    # lint
```

Tests stub every upstream call, so they need no credentials and no network. CI
runs lint, tests, and a full Docker build that boots the container and checks it
answers `/health`.

After retraining, regenerate the derived artifacts:

```bash
python scripts/export_label_encoder.py
python -m skylens.pipeline.generate_airport_profile
```

---

## Limitations

- **Single instance.** The score cache is process memory and peak state is a JSON
  file. Two replicas would compute different scores and race on that file.
  Moving this state to Postgres is the next step.
- **Upstream sweeps are sequential** — a full pass takes ~83 seconds, which is why
  refresh is on a timer rather than on demand.
- **No auth or rate limiting.** Intended for a trusted network today.
- **Coverage gaps.** OpenSky's receiver network is thin over parts of Asia and the
  oceans; affected airports are flagged rather than silently zeroed.

## Stack

FastAPI · APScheduler · XGBoost · NumPy · Polars · Docker · React Native (Expo) ·
OpenSky Network · Open-Meteo
