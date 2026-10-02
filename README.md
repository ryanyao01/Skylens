# SkyLens

[![CI](https://github.com/ryanyao01/Skylens/actions/workflows/ci.yml/badge.svg)](https://github.com/ryanyao01/Skylens/actions/workflows/ci.yml)

Real-time airport congestion scoring and delay-cascade forecasting for 58 airports
worldwide — with a warehouse that records every run, data-quality checks on every
refresh, and a backtest that measures whether the cascade model predicts anything.

SkyLens answers two questions: **how busy is this airport right now, relative to
what it can handle**, and **if it is overloaded, which airports get hit next**.

> Your flight usually isn't delayed by weather where you are. It's delayed by
> weather somewhere your plane was three hours ago.

Open the dashboard at `http://localhost:8080/` once it's running.

---

## How it works

```
                    ┌─────────────── every 15 minutes ───────────────┐
OpenSky Network ──► │ 1 global request ─► count aircraft in 58 boxes │
Open-Meteo     ───► │ 1 batched request ─► wind / rain / visibility   │
                    │        │                                        │
                    │        ▼                                        │
                    │  score  ◄── XGBoost q10/q50/q90 (local time)    │
                    │    │    ◄── calibrated peak density             │
                    │    ▼                                            │
                    │  cascade simulation (propagation graph)         │
                    │    │                                            │
                    │    ├──► 10 data-quality checks                  │
                    │    └──► DuckDB warehouse (raw → facts → marts)  │
                    └────────────────────────────────────────────────┘
                             │                         │
                     in-memory cache               SQL marts
                             │                         │
                             └──────► FastAPI ◄────────┘
                                         │
                          web dashboard (/)  ·  Expo mobile app
```

A full refresh takes about **5 seconds**. Requests read the in-memory cache or
the warehouse; no request ever blocks on an upstream API.

### The congestion score

```
score = live_aircraft / (peak_density × weather_penalty) × 100      capped at 100
```

- **`live_aircraft`** — aircraft inside the airport's bounding box. A *density*
  snapshot, not an arrival count.
- **`peak_density`** — that airport's busiest observed density. Seeded from the
  trained model (below) and raised whenever a higher live value is observed.
- **`weather_penalty`** — 0.5 to 1.0 from wind, gusts, precipitation and
  visibility. Bad weather shrinks capacity, so the same traffic scores higher.

A score of **65 or more** triggers the cascade simulation: a learned route graph
is walked breadth-first for 6 hours with 0.6 decay per hop, estimating which
airports feel the delay next.

---

## The model, honestly

Three XGBoost quantile regressors (q10/q50/q90) predict **arrivals per 15-minute
slot** from `(local hour, quarter-hour, day of week, month, weekend, historical
slot mean, airport)`, trained on 43 US airports.

| model | MAE (arrivals per 15-min slot) |
|---|---|
| baseline (historical slot mean) | 0.4670 |
| XGBoost, no airport encoding | 0.4598 |
| XGBoost, with airport encoding | **0.4581** |

A **1.9% improvement over the naive baseline** — real but modest. Where the model
earns its place is what an average cannot do: a 10th–90th percentile uncertainty
band, and interactions between hour, day and airport.

**Where it reaches the product:**

1. **Peak calibration (offline).** The models predict arrivals; OpenSky reports
   density — different units. Fitting `density ≈ k × model_peak_capacity` on 10
   airports with both measured gives **k ≈ 21.96**, replacing a hardcoded constant
   that 33 of 58 airports used to fall back to.
2. **Demand forecast (live).** Every refresh predicts the next hour at
   q10/q50/q90: `forecast_next_hour`, `demand_trend` and `projected_score`.

**Training/serving skew, found and fixed.** The models were trained on BTS
`CRS_ARR_TIME`, which is *local* time, but the service fed them UTC — so at 3am in
Atlanta it forecast the 7am rush. Features now use each airport's IANA time zone,
and a regression test pins the behaviour.

---

## The warehouse

Every refresh is persisted to DuckDB — one file on the state volume, no server —
in the layers a dbt project would use:

| layer | objects | purpose |
|---|---|---|
| raw | `raw_observations` | what came back from upstream, per airport per run |
| core | `fact_airport_scores`, `fact_cascade_predictions`, `ingestion_runs`, `dq_results`, `dim_airports` | the modelled record |
| staging | `stg_scores`, `stg_cascade_predictions` | trustworthy rows only: failed runs and `no_states` airports excluded |
| intermediate | `int_cascade_outcomes` | each prediction matched to what actually happened |
| marts | `mart_airport_hourly`, `mart_airport_leaderboard`, `mart_cascade_backtest`, `mart_pipeline_health`, `mart_data_quality` | the questions the dashboard and API answer |

The SQL lives in [`src/skylens/sql/`](src/skylens/sql) as plain files, laid out to
port to dbt directly. Runs are written atomically — all tables or none.

### Does the cascade model work? The backtest

[`int_cascade_outcomes`](src/skylens/sql/intermediate/int_cascade_outcomes.sql)
takes every run where the cascade fired and uses a DuckDB `ASOF JOIN` to find
each airport's score 1–6 hours later. Airports the cascade **named** are compared
against airports it **did not name** over the *same* windows — the null model in
which nothing propagates. That cancels out effects that move every airport at
once, like the morning ramp-up.

[`mart_cascade_backtest`](src/skylens/sql/marts/mart_cascade_backtest.sql) reports
the lift (mean change, named minus control) and a Welch t statistic per horizon.
`GET /analytics/cascade-backtest` withholds a verdict until 30 predictions have
matured. Tests seed synthetic data with a known effect and confirm the method
detects it — and reports nothing when there is nothing.

**Known weakness:** named airports are graph neighbours of busy hubs, not a random
sample. A stronger null would compare each airport against its own typical change
at the same local hour.

---

## Data quality

Ten checks run after every refresh and are recorded in `dq_results`. Unit tests
prove the code is right; these prove the data is.

| check | severity | catches |
|---|---|---|
| `opensky_request_ok` | critical | upstream failure, quota exhaustion |
| `opensky_data_fresh` | critical | stale or cached state vectors (> 10 min) |
| `all_airports_scored` | critical | a missing airport |
| `score_in_range` | critical | NaN or values outside 0–100 |
| `live_data_coverage` | warning | fewer than 90% of airports with live data |
| `weather_coverage` | warning | more than 10% of airports missing weather |
| `aircraft_volume_plausible` | warning | HTTP 200 with a near-empty sky |
| `aircraft_volume_stable` | warning | run-over-run swings over 50% |
| `api_quota_headroom` | warning | fewer than 400 OpenSky credits left |
| `forecast_quantiles_ordered` | warning | p10 > p50 or p50 > p90 |

If the upstream request fails, the API **keeps serving the last good scores**
rather than an all-zero map, and `/health` reports the degradation.

### Why one global request

OpenSky allows 4,000 credits a day. The original design made one bounding-box
query per airport — 58 × 96 refreshes = 5,568 credits — so a continuously running
deployment exhausted its quota after about 17 hours and every airport silently
went to zero until midnight UTC. A single worldwide query costs 4 credits and
returns the same aircraft; the boxes are applied locally. **384 credits a day**,
and ~2 seconds instead of ~80.

---

## Quickstart

### Docker (recommended)

```bash
cp .env.example .env    # add your OpenSky credentials
docker compose up --build
```

Scores are ready about 10 seconds after the container starts. Then open
<http://localhost:8080/> for the dashboard, or:

```bash
curl http://localhost:8080/health
```

### Local

```bash
pip install -e ".[dev]"
uvicorn skylens.api.main:app --host 0.0.0.0 --port 8080 --reload
```

---

## API

Interactive docs at `/docs`.

| Endpoint | Description |
|---|---|
| `GET /` | The dashboard |
| `GET /airports/scores` | Every airport's live score, forecast, weather and coordinates |
| `GET /airports/{icao}/score` | One airport (case-insensitive) |
| `GET /forecast/cascade` · `/{icao}` | Current delay cascades |
| `GET /health` | Cache state, last refresh, data-quality verdict, warehouse status |
| `GET /quality` | Every check's latest result and historical pass rate |
| `GET /pipeline/runs` · `/pipeline/daily` | Ingestion history and daily health |
| `GET /analytics/leaderboard` | Airports most often under stress |
| `GET /analytics/hourly/{icao}` | Typical congestion by local hour |
| `GET /analytics/history/{icao}` | Score time series |
| `GET /analytics/cascade-backtest` | Does the cascade predict anything? |

Every airport carries `live_data_status`. OpenSky receiver coverage is thin over
parts of East Asia, so zero aircraft can mean an empty sky *or* no reception —
`no_states` distinguishes them, and clients should not render it as quiet.

---

## Configuration

All settings are environment variables; see [`.env.example`](.env.example).

| Variable | Default | Purpose |
|---|---|---|
| `OPENSKY_CLIENT_ID` / `_SECRET` | — | **Required.** OpenSky OAuth credentials |
| `SKYLENS_REFRESH_SECONDS` | `900` | Seconds between refreshes (min 60) |
| `SKYLENS_STATE_DIR` | `data/clean` | Peak observations and the warehouse |
| `SKYLENS_WAREHOUSE_ENABLED` | `true` | Persist every run to DuckDB |
| `SKYLENS_MODELS_DIR` | `models/` | Model artifacts |
| `SKYLENS_CORS_ALLOW_ORIGINS` | `*` | Comma-separated allowlist |
| `SKYLENS_LOG_FORMAT` | `text` | `text`, or `json` for log aggregators |

**`SKYLENS_STATE_DIR` must be persistent in production.** It holds the warehouse
and the learned peak densities that form the score denominator. On an ephemeral
filesystem both reset on every deploy. `docker-compose.yml` mounts a named volume
for exactly this reason.

---

## Layout

```
src/skylens/
  airports.py                  The 58 airports: coordinates and time zones
  api/main.py                  FastAPI app, scheduler, refresh pipeline
  pipeline/opensky.py          Global OpenSky request, box counts, peak state
  pipeline/weather.py          Batched Open-Meteo request
  pipeline/scorer.py           Score formula + quantile demand forecast
  pipeline/cascade.py          Delay propagation simulation
  warehouse.py                 DuckDB persistence and SQL model builds
  quality.py                   The ten data-quality checks
  sql/                         staging -> intermediate -> marts
  web/index.html               The dashboard
models/                        xgb_q10/q50/q90, label encoder, propagation graph
notebooks/                     EDA, feature engineering, training, cascade graph
tests/                         141 tests, no network access
```

---

## Development

```bash
pytest                       # 141 tests, ~85% coverage
ruff check src scripts tests # lint
```

Tests stub every upstream call, so they need no credentials or network. CI runs
lint, tests, and a Docker build that boots the container and checks `/health`.

After retraining, regenerate the derived artifacts:

```bash
python scripts/export_label_encoder.py
python -m skylens.pipeline.generate_airport_profile
```

---

## Limitations

- **A fresh volume reads high for a while.** Each refresh records the current
  count as a new peak *before* scoring, so on an empty volume any airport busier
  than its calibrated baseline scores exactly 100 until real peaks accumulate —
  roughly a day of collection.
- **Bounding boxes overlap.** The LGA box lies entirely inside JFK's, and EWR,
  MDW and DCA overlap their neighbours by a third or more, so nearby airports
  count each other's aircraft.
- **Coarse capacity estimates.** 24 of 43 trained airports have `peak_capacity`
  pinned at an upstream floor of 2.00 arrivals/slot, so their calibrated peaks
  cluster.
- **The backtest needs time.** Predictions mature 1–6 hours after they are made;
  a verdict needs at least a few days of continuous collection.
- **Single instance.** The live cache is process memory and DuckDB allows one
  writer. Scaling out would mean Postgres.
- **No auth or rate limiting.** Intended for a trusted network.

## Stack

FastAPI · APScheduler · DuckDB · XGBoost · NumPy · Leaflet · Docker · GitHub
Actions · React Native (Expo) · OpenSky Network · Open-Meteo
