"""DuckDB warehouse: every refresh, persisted and queryable.

Layers, the same ones dbt projects use:

    raw_observations        what came back from upstream, per airport per run
    fact_airport_scores     the scored result, one row per airport per run
    fact_cascade_predictions  every downstream impact the cascade predicted
    ingestion_runs          one row per refresh: timings, credits, failures
    dq_results              one row per data-quality check per run
    dim_airports            reference data

    sql/staging/*.sql       views: only trustworthy rows, cleaned
    sql/intermediate/*.sql  views: joins the marts build on
    sql/marts/*.sql         views: the questions the dashboard and API answer

DuckDB is a single file with no server, which suits one process on one volume.
All timestamps are stored as UTC ``TIMESTAMP`` (no time zone), so no ICU
extension is needed at runtime; local-time fields are computed in Python.

Thread model: the scheduler thread writes, request threads read. A DuckDB
connection is not thread-safe, so every operation takes its own cursor, and
writes are additionally serialised with a lock.

Write path: rows go in as ONE JSON string parameter that DuckDB's built-in
JSON reader expands, not as one Python parameter per value. Measured on this
driver, binding 58 rows of Python parameters costs ~200 ms; the same rows as a
single JSON parameter cost ~2 ms. DuckDB itself inserts 58,000 rows in ~13 ms,
so the binding layer, not the database, was the bottleneck. The data stays
parameterised either way -- nothing is spliced into SQL text.
"""

from __future__ import annotations

import json
import math
import threading
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import duckdb

from skylens.airports import AIRPORTS
from skylens.logging_config import get_logger

logger = get_logger(__name__)

SQL_LAYERS = ("staging", "intermediate", "marts")

SCHEMA = """
CREATE TABLE IF NOT EXISTS dim_airports (
    code        VARCHAR PRIMARY KEY,
    name        VARCHAR NOT NULL,
    lat         DOUBLE  NOT NULL,
    lon         DOUBLE  NOT NULL,
    tz          VARCHAR NOT NULL,
    has_model   BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id              VARCHAR PRIMARY KEY,
    started_at          TIMESTAMP NOT NULL,   -- UTC
    finished_at         TIMESTAMP NOT NULL,   -- UTC
    duration_s          DOUBLE,
    opensky_status      VARCHAR,
    opensky_attempts    INTEGER,
    credits_remaining   INTEGER,
    aircraft_worldwide  INTEGER,
    weather_missing     INTEGER,
    airports_scored     INTEGER,
    airports_degraded   INTEGER,
    cascade_triggers    INTEGER,
    error               VARCHAR
);

CREATE TABLE IF NOT EXISTS raw_observations (
    run_id          VARCHAR   NOT NULL,
    observed_at     TIMESTAMP NOT NULL,       -- UTC
    airport         VARCHAR   NOT NULL,
    aircraft_count  INTEGER,
    data_status     VARCHAR,
    wind_kn         DOUBLE,
    gusts_kn        DOUBLE,
    precip_mm       DOUBLE,
    visibility_m    DOUBLE,
    weather_code    INTEGER
);

CREATE TABLE IF NOT EXISTS fact_airport_scores (
    run_id             VARCHAR   NOT NULL,
    observed_at        TIMESTAMP NOT NULL,    -- UTC
    airport            VARCHAR   NOT NULL,
    local_hour         INTEGER,
    local_dow          INTEGER,               -- 1 = Monday
    score              DOUBLE,
    projected_score    DOUBLE,
    live_flights       INTEGER,
    live_peak_count    INTEGER,
    peak_source        VARCHAR,
    weather_penalty    DOUBLE,
    expected_arrivals  DOUBLE,
    forecast_p10       DOUBLE,
    forecast_p50       DOUBLE,
    forecast_p90       DOUBLE,
    demand_trend       VARCHAR,
    forecast_source    VARCHAR,
    data_status        VARCHAR,
    model_trained      BOOLEAN
);

CREATE TABLE IF NOT EXISTS fact_cascade_predictions (
    run_id            VARCHAR   NOT NULL,
    predicted_at      TIMESTAMP NOT NULL,     -- UTC
    trigger_airport   VARCHAR   NOT NULL,
    trigger_score     DOUBLE,
    horizon_h         INTEGER   NOT NULL,
    impacted_airport  VARCHAR   NOT NULL,
    predicted_impact  DOUBLE
);

CREATE TABLE IF NOT EXISTS dq_results (
    run_id       VARCHAR   NOT NULL,
    checked_at   TIMESTAMP NOT NULL,          -- UTC
    check_name   VARCHAR   NOT NULL,
    severity     VARCHAR   NOT NULL,          -- critical | warning
    passed       BOOLEAN   NOT NULL,
    observed     VARCHAR,
    expectation  VARCHAR
);
"""


def _utc(moment: datetime) -> datetime:
    """Naive UTC, the storage convention for every timestamp column."""
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(UTC).replace(tzinfo=None)


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, float) and not math.isfinite(value):
        return None  # NaN/inf are not valid JSON; the DQ checks flag them upstream
    return value


def _sql_files() -> list[tuple[str, str]]:
    """(name, sql) for every model, in dependency order: staging -> marts."""
    root = resources.files("skylens") / "sql"
    ordered: list[tuple[str, str]] = []
    for layer in SQL_LAYERS:
        folder = root / layer
        if not folder.is_dir():
            continue
        for entry in sorted(folder.iterdir(), key=lambda e: e.name):
            if entry.name.endswith(".sql"):
                ordered.append((f"{layer}/{entry.name}", entry.read_text(encoding="utf-8")))
    return ordered


class Warehouse:
    def __init__(self, path: Path | str, trained_airports: set[str] | None = None) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(str(path))
        self._write_lock = threading.Lock()
        self._column_cache: dict[str, list[tuple[str, str]]] = {}
        self.migrate(trained_airports or set())

    # ------------------------------------------------------------ lifecycle
    def migrate(self, trained_airports: set[str]) -> None:
        """Create tables if missing, refresh reference data, (re)build views."""
        with self._write_lock:
            cur = self._con.cursor()
            cur.execute(SCHEMA)
            self._insert(
                cur,
                "dim_airports",
                [
                    (a.code, a.name, a.lat, a.lon, a.tz, a.code in trained_airports)
                    for a in AIRPORTS.values()
                ],
                verb="INSERT OR REPLACE",
            )
            for name, sql in _sql_files():
                try:
                    cur.execute(sql)
                except duckdb.Error as e:
                    raise RuntimeError(f"SQL model {name} failed to build: {e}") from e
        logger.info("warehouse ready", extra={"path": str(self.path), "models": len(_sql_files())})

    def close(self) -> None:
        self._con.close()

    def _columns(self, table: str) -> list[tuple[str, str]]:
        """(name, type) for every column, read from the catalogue -- one schema, one place."""
        if table not in self._column_cache:
            self._column_cache[table] = self._con.cursor().execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = ? ORDER BY ordinal_position",
                [table],
            ).fetchall()
        return self._column_cache[table]

    def _insert(
        self, cur: duckdb.DuckDBPyConnection, table: str, rows: list[tuple],
        verb: str = "INSERT",
    ) -> None:
        """Insert many rows through a single JSON parameter (see module docstring)."""
        if not rows:
            return
        columns = self._columns(table)
        names = [name for name, _ in columns]
        payload = json.dumps(
            [{n: _json_value(v) for n, v in zip(names, row, strict=True)} for row in rows]
        )
        schema = json.dumps(dict(columns))  # column names and types from our own catalogue
        cur.execute(
            f"{verb} INTO {table} "
            # _strict: a value that does not fit its column raises. Plain from_json
            # would silently store NULL instead -- quiet corruption in a warehouse.
            f"SELECT unnest(from_json_strict(?::JSON, '[{schema}]'), recursive := true)",
            [payload],
        )

    # ---------------------------------------------------------------- reads
    def query(self, sql: str, params: list | tuple | None = None) -> list[dict[str, Any]]:
        cur = self._con.cursor()
        cur.execute(sql, params or [])
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]

    def scalar(self, sql: str, params: list | tuple | None = None) -> Any:
        rows = self._con.cursor().execute(sql, params or []).fetchone()
        return rows[0] if rows else None

    def previous_run_aircraft_total(self) -> int | None:
        """Total aircraft across tracked airports in the last successful run."""
        return self.scalar(
            """
            SELECT sum(o.aircraft_count)
            FROM raw_observations o
            WHERE o.run_id = (
                SELECT run_id FROM ingestion_runs
                WHERE opensky_status = 'ok'
                ORDER BY started_at DESC LIMIT 1
            )
            """
        )

    # --------------------------------------------------------------- writes
    def record_run(
        self,
        *,
        run_id: str,
        started_at: datetime,
        finished_at: datetime,
        flight_counts: dict,
        weather: dict,
        scores: dict,
        cascade: dict,
        error: str | None = None,
    ) -> None:
        """Persist one refresh atomically: either every table gets it or none."""
        observed_at = _utc(started_at)
        metadata = flight_counts.get("_metadata", {})
        run = flight_counts.get("_run", {})

        raw_rows = []
        for code in AIRPORTS:
            w = weather.get(code) or {}
            raw_rows.append((
                run_id, observed_at, code,
                flight_counts.get(code) if isinstance(flight_counts.get(code), int) else None,
                metadata.get(code, {}).get("status"),
                w.get("wind_speed_kn"), w.get("wind_gusts_kn"), w.get("precipitation_mm"),
                w.get("visibility_m"), w.get("weather_code"),
            ))

        score_rows = []
        for code, d in scores.items():
            local = datetime.fromisoformat(d["local_time"]) if d.get("local_time") else None
            f = d.get("forecast_next_hour") or {}
            score_rows.append((
                run_id, observed_at, code,
                local.hour if local else None, local.isoweekday() if local else None,
                d.get("score"), d.get("projected_score"), d.get("live_flights"),
                d.get("live_peak_count"), d.get("peak_source"), d.get("weather_penalty"),
                d.get("expected_arrivals"), f.get("p10"), f.get("p50"), f.get("p90"),
                d.get("demand_trend"), d.get("forecast_source"), d.get("live_data_status"),
                d.get("model_trained"),
            ))

        cascade_rows = []
        for trigger, by_hour in cascade.items():
            trigger_score = (scores.get(trigger) or {}).get("score")
            for hour, impacted in by_hour.items():
                for airport, impact in impacted.items():
                    cascade_rows.append((
                        run_id, observed_at, trigger, trigger_score, int(hour), airport, impact,
                    ))

        degraded = sum(1 for m in metadata.values() if m.get("status") != "ok")
        weather_missing = sum(1 for code in AIRPORTS if not weather.get(code))
        run_row = (
            run_id, observed_at, _utc(finished_at),
            round((finished_at - started_at).total_seconds(), 2),
            run.get("status"), run.get("attempts"), run.get("credits_remaining"),
            run.get("aircraft_worldwide"), weather_missing, len(scores), degraded,
            len(cascade), error,
        )

        with self._write_lock:
            cur = self._con.cursor()
            cur.begin()
            try:
                self._insert(cur, "ingestion_runs", [run_row])
                self._insert(cur, "raw_observations", raw_rows)
                self._insert(cur, "fact_airport_scores", score_rows)
                self._insert(cur, "fact_cascade_predictions", cascade_rows)
                cur.commit()
            except Exception:
                cur.rollback()
                raise

    def record_quality(self, run_id: str, checked_at: datetime, results: list[dict]) -> None:
        rows = [
            (run_id, _utc(checked_at), r["check_name"], r["severity"], r["passed"],
             str(r.get("observed")), r.get("expectation"))
            for r in results
        ]
        with self._write_lock:
            self._insert(self._con.cursor(), "dq_results", rows)


# ---------------------------------------------------------------- singleton
_warehouse: Warehouse | None = None
_singleton_lock = threading.Lock()


def open_warehouse(path: Path, trained_airports: set[str]) -> Warehouse:
    global _warehouse
    with _singleton_lock:
        if _warehouse is None:
            _warehouse = Warehouse(path, trained_airports)
        return _warehouse


def get_warehouse() -> Warehouse | None:
    return _warehouse


def close_warehouse() -> None:
    global _warehouse
    with _singleton_lock:
        if _warehouse is not None:
            _warehouse.close()
            _warehouse = None
