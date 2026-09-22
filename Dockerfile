# syntax=docker/dockerfile:1
#
# SkyLens API image.
#
# Python 3.14 is chosen deliberately: it is what the project is developed and
# tested on, and scipy 1.18.1 (pulled in by xgboost) publishes no cp311 wheel,
# so a 3.11 base would try to compile scipy from source.
#
# Build:  docker build -t skylens-api .
# Run:    docker run --rm -p 8080:8080 --env-file .env \
#                 -v skylens-state:/var/lib/skylens skylens-api

# ---------------------------------------------------------------------------
# Stage 1 — build dependencies into a self-contained virtualenv
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Dependencies first, in their own layer: this only re-runs when
# requirements.txt changes, not on every source edit. All pinned packages ship
# manylinux wheels for cp314, so no compiler toolchain is needed here.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Then the package itself. --no-deps because requirements.txt already resolved
# everything and we do not want a second, unpinned resolution.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-deps .

# ---------------------------------------------------------------------------
# Stage 2 — runtime
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    SKYLENS_MODELS_DIR=/app/models \
    SKYLENS_DATA_DIR=/app/data \
    SKYLENS_STATE_DIR=/var/lib/skylens \
    SKYLENS_LOG_FORMAT=json

# libgomp is required by xgboost (OpenMP runtime) and is not in the slim base.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 skylens

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Model artifacts and the airport profile are read-only inputs. They are baked
# into the image so the container has no external dependency at startup.
COPY --chown=skylens:skylens models/ /app/models/
COPY --chown=skylens:skylens data/clean/airport_runtime_profile.json /app/data/clean/

# The one directory the service writes to. Mount a volume here or the learned
# peak observations are lost on every container replacement, which silently
# shifts every airport's score. See docker-compose.yml.
RUN mkdir -p /var/lib/skylens && chown -R skylens:skylens /var/lib/skylens
VOLUME ["/var/lib/skylens"]

USER skylens

EXPOSE 8080

# Liveness, not readiness. Deliberately checks only that the process answers,
# not that status == "ok": the first scoring pass takes ~2 minutes, and an
# upstream OpenSky outage marks the service degraded without meaning the
# container should be killed and replaced.
HEALTHCHECK --interval=30s --timeout=5s --start-period=240s --retries=3 \
    CMD ["python", "-c", "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT','8080')}/health\", timeout=4).status==200 else 1)"]

# sh -c so $PORT can be injected by the platform (Render, Cloud Run, Heroku);
# exec so uvicorn becomes PID 1 and receives SIGTERM directly.
CMD ["sh", "-c", "exec uvicorn skylens.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
