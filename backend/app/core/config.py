"""Application settings loaded from environment variables (prefix ``TPORT_``)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TPORT_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # Comma-free JSON list in env, e.g. TPORT_CORS_ORIGINS='["https://tport.example"]'
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:2028"])

    # Local time zone used to decide what "today" means for date validation.
    market_timezone: str = "Asia/Tashkent"
    search_max_days_ahead: int = Field(default=90, ge=1, le=365)
    search_max_page_size: int = Field(default=50, ge=1, le=200)

    # Data freshness thresholds, measured from the time the provider data was retrieved.
    data_stale_after_seconds: int = Field(default=15 * 60, ge=1)
    data_expire_after_seconds: int = Field(default=6 * 60 * 60, ge=1)

    # Per-client fixed-window rate limit (in-memory; single-process only).
    rate_limit_per_minute: int = Field(default=120, ge=1)
    auth_rate_limit_per_minute: int = Field(default=10, ge=1)  # register/login/logout per IP
    ai_rate_limit_per_minute: int = Field(default=20, ge=1)

    enable_demo_provider: bool = True
    # "live": demo adapter generates data on request. "stored": serve the latest imported
    # snapshot from the database (populated by `python -m app.cli import-demo`).
    demo_provider_mode: Literal["live", "stored"] = "live"

    # --- database -------------------------------------------------------------------
    database_url: str = "postgresql+psycopg://tport:tport@127.0.0.1:5432/tport"
    database_echo: bool = False

    # --- sessions & auth ---------------------------------------------------------------
    session_cookie_name: str = "tport_session"
    csrf_cookie_name: str = "tport_csrf"
    session_ttl_hours: int = Field(default=24 * 14, ge=1, le=24 * 90)
    # Force the Secure cookie flag. Always on in production regardless of this value.
    cookie_secure: bool = False
    max_saved_journeys_per_user: int = Field(default=200, ge=1)

    # --- AI interpreter -------------------------------------------------------------------
    # "rules" = deterministic parser only (no external calls). "anthropic" = LLM with
    # validated JSON output, falling back to rules on any failure.
    ai_engine: Literal["rules", "anthropic"] = "rules"
    ai_api_key: str | None = Field(default=None, repr=False)
    ai_model: str = "claude-haiku-5-5"
    ai_timeout_seconds: float = Field(default=8.0, gt=0, le=30)
    ai_max_input_chars: int = Field(default=500, ge=20, le=2000)

    # --- multimodal routing ---------------------------------------------------------------
    transfer_min_minutes_same_station: int = Field(default=20, ge=0)
    transfer_min_minutes_station_change: int = Field(default=60, ge=0)
    transfer_min_minutes_to_flight: int = Field(default=120, ge=0)
    transfer_max_wait_minutes: int = Field(default=6 * 60, ge=30)

    # Bearer token for /health/providers and /metrics. Unset = those endpoints return 404.
    ops_token: SecretStr | None = Field(default=None, repr=False)

    # Activity data retention (journey_searches, ai_requests); see `python -m app.cli purge-activity`.
    activity_retention_days: int = Field(default=180, ge=1)

    @model_validator(mode="after")
    def _production_safety(self) -> Settings:
        """Refuse to start in production with development defaults."""
        if self.environment != "production":
            return self
        problems = []
        if "tport:tport@" in self.database_url or "change-me" in self.database_url:
            problems.append("TPORT_DATABASE_URL uses a development password")
        if not self.cors_origins or any(not o.startswith("https://") for o in self.cors_origins):
            problems.append("TPORT_CORS_ORIGINS must list only https:// origins")
        if self.ops_token and len(self.ops_token.get_secret_value()) < 32:
            problems.append("TPORT_OPS_TOKEN must be at least 32 characters")
        if self.database_echo:
            problems.append("TPORT_DATABASE_ECHO must be off (it logs query parameters)")
        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def secure_cookies(self) -> bool:
        return self.is_production or self.cookie_secure


@lru_cache
def get_settings() -> Settings:
    return Settings()
