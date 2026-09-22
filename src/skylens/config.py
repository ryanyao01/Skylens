"""Central configuration for SkyLens.

Every tunable value and filesystem path is resolved here, exactly once, from the
environment. Modules import ``settings`` rather than reading ``os.getenv`` or
recomputing ``Path(__file__).parents[n]`` on their own.

Paths default to a layout relative to the installed package (which matches the
repository during local development) but are individually overridable, so a
container can mount models and mutable data anywhere.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# src/skylens/config.py -> src/skylens -> src -> <repo root>
PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_PROJECT_ROOT = PACKAGE_DIR.parents[1]


class Settings(BaseSettings):
    """Runtime configuration, read from the environment and an optional .env file."""

    # env_file is absolute on purpose: a bare ".env" resolves against the
    # current working directory, so credentials load when started from the repo
    # root and silently do not when started from anywhere else (a container
    # WORKDIR, a service manager). A missing file is simply ignored, which is
    # the normal case in a container where config arrives as real env vars.
    model_config = SettingsConfigDict(
        env_file=DEFAULT_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    # --- credentials -----------------------------------------------------
    opensky_client_id: str | None = Field(
        default=None, validation_alias="OPENSKY_CLIENT_ID"
    )
    opensky_client_secret: str | None = Field(
        default=None, validation_alias="OPENSKY_CLIENT_SECRET"
    )

    # --- filesystem ------------------------------------------------------
    project_root: Path = Field(
        default=DEFAULT_PROJECT_ROOT, validation_alias="SKYLENS_PROJECT_ROOT"
    )
    models_dir: Path | None = Field(default=None, validation_alias="SKYLENS_MODELS_DIR")
    data_dir: Path | None = Field(default=None, validation_alias="SKYLENS_DATA_DIR")
    state_dir: Path | None = Field(default=None, validation_alias="SKYLENS_STATE_DIR")

    # --- scheduling ------------------------------------------------------
    refresh_interval_seconds: int = Field(
        default=900, ge=60, validation_alias="SKYLENS_REFRESH_SECONDS"
    )
    write_runtime_json: bool = Field(
        default=False, validation_alias="SKYLENS_WRITE_RUNTIME_JSON"
    )

    # --- upstream APIs ---------------------------------------------------
    http_timeout_seconds: float = Field(
        default=10.0, gt=0, validation_alias="SKYLENS_HTTP_TIMEOUT"
    )
    opensky_request_delay_seconds: float = Field(
        default=0.5, ge=0, validation_alias="SKYLENS_OPENSKY_DELAY"
    )

    # --- service ---------------------------------------------------------
    # Stored as a plain string, not list[str], on purpose. pydantic-settings
    # JSON-decodes env values for complex types inside the settings source,
    # before any field validator runs, so SKYLENS_CORS_ALLOW_ORIGINS="*" would
    # fail as invalid JSON. Parsed into a list by the cors_origins property.
    cors_allow_origins_raw: str = Field(
        default="*", validation_alias="SKYLENS_CORS_ALLOW_ORIGINS"
    )
    log_level: str = Field(default="INFO", validation_alias="SKYLENS_LOG_LEVEL")
    log_format: str = Field(default="text", validation_alias="SKYLENS_LOG_FORMAT")

    @property
    def cors_allow_origins(self) -> list[str]:
        """Allowed CORS origins, from a comma-separated env value."""
        origins = [o.strip() for o in self.cors_allow_origins_raw.split(",") if o.strip()]
        return origins or ["*"]

    @field_validator("log_format")
    @classmethod
    def _check_log_format(cls, value: str) -> str:
        if value not in {"text", "json"}:
            raise ValueError("log_format must be 'text' or 'json'")
        return value

    # Derived paths. Each falls back to the conventional repository layout so
    # local development needs no environment variables at all.
    @property
    def models_path(self) -> Path:
        return self.models_dir or self.project_root / "models"

    @property
    def data_path(self) -> Path:
        return self.data_dir or self.project_root / "data"

    @property
    def clean_data_path(self) -> Path:
        return self.data_path / "clean"

    @property
    def state_path(self) -> Path:
        """Directory for data the service *writes* at runtime.

        Kept separate from ``clean_data_path`` because this is the only location
        the service mutates, which makes it the one directory a container must
        mount as a writable volume.
        """
        return self.state_dir or self.clean_data_path

    @property
    def airport_profile_file(self) -> Path:
        return self.clean_data_path / "airport_runtime_profile.json"

    @property
    def peak_observations_file(self) -> Path:
        return self.state_path / "live_peak_observations.json"

    @property
    def cascade_forecast_file(self) -> Path:
        return self.state_path / "cascade_forecast.json"

    @property
    def live_scores_file(self) -> Path:
        return self.state_path / "live_scores.json"

    @property
    def label_encoder_file(self) -> Path:
        return self.models_path / "label_encoder.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, parsed once."""
    return Settings()


settings = get_settings()
