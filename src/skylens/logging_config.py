"""Logging setup for SkyLens.

Replaces ad-hoc ``print`` calls with the standard library ``logging`` module so
output carries a level, a timestamp and the emitting module, and so log
verbosity is controlled by configuration rather than by editing source.

Set ``SKYLENS_LOG_FORMAT=json`` to emit one JSON object per line, which is what
a log aggregator (CloudWatch, Loki, Datadog) expects from a container.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from skylens.config import settings

# Attributes present on every LogRecord; anything else was attached by the
# caller via `extra=` and belongs in the structured payload.
_STANDARD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """Render each record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=UTC
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Install handlers on the root logger. Safe to call more than once."""
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    for existing in list(root.handlers):
        root.removeHandler(existing)

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s %(name)-28s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
    root.addHandler(handler)

    # Uvicorn installs its own handlers with propagate=False, so its startup
    # banner and access log would bypass the formatter above and break an
    # otherwise-parseable JSON log stream. Hand those loggers back to the root.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    # These are chatty at DEBUG and drown out anything useful.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
