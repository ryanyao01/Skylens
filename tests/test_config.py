"""Settings must parse correctly from real environment variables.

Every case here runs in a subprocess with a scrubbed environment, because
pydantic-settings reads the environment once at import time.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

PARSE = "from skylens.config import Settings; s=Settings(); print(s.cors_allow_origins)"


def _run(snippet: str, **env_overrides) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SKYLENS_", "OPENSKY_"))}
    env["SKYLENS_PROJECT_ROOT"] = os.getcwd()
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", snippet], env=env, capture_output=True, text=True
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("*", "['*']"),
        ("https://a.example.com", "['https://a.example.com']"),
        ("https://a.example.com,http://localhost:8081",
         "['https://a.example.com', 'http://localhost:8081']"),
        (" https://a.example.com , http://b.example.com ",
         "['https://a.example.com', 'http://b.example.com']"),
    ],
)
def test_cors_origins_parse_from_env(value, expected):
    """Regression: a bare '*' used to crash at import.

    pydantic-settings JSON-decodes list-typed fields inside the settings source,
    before field validators run, so '*' failed as invalid JSON and the container
    crash-looped. The field is a plain string now, split by a property.
    """
    result = _run(PARSE, SKYLENS_CORS_ALLOW_ORIGINS=value)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_cors_defaults_to_wildcard_when_unset():
    result = _run(PARSE)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "['*']"


@pytest.mark.parametrize(
    ("var", "value"),
    [
        ("SKYLENS_REFRESH_SECONDS", "900"),
        ("SKYLENS_WRITE_RUNTIME_JSON", "1"),
        ("SKYLENS_HTTP_TIMEOUT", "10"),
        ("SKYLENS_OPENSKY_DELAY", "0.5"),
        ("SKYLENS_LOG_LEVEL", "DEBUG"),
        ("SKYLENS_LOG_FORMAT", "json"),
        ("SKYLENS_MODELS_DIR", "/app/models"),
        ("SKYLENS_STATE_DIR", "/var/lib/skylens"),
    ],
)
def test_every_documented_env_var_is_accepted(var, value):
    result = _run("from skylens.config import Settings; Settings()", **{var: value})
    assert result.returncode == 0, f"{var}={value} rejected:\n{result.stderr}"


@pytest.mark.parametrize(
    ("var", "value"),
    [
        ("SKYLENS_LOG_FORMAT", "xml"),      # not text/json
        ("SKYLENS_REFRESH_SECONDS", "5"),   # below the 60s floor
        ("SKYLENS_HTTP_TIMEOUT", "0"),      # must be > 0
    ],
)
def test_invalid_values_are_rejected(var, value):
    result = _run("from skylens.config import Settings; Settings()", **{var: value})
    assert result.returncode != 0, f"{var}={value} should have been rejected"
