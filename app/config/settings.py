"""Application settings loaded from environment via Pydantic Settings.

All secrets are read from environment variables / .env file. Nothing is
hardcoded. The :data:`settings` singleton is imported throughout the app.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root: task_manager_bot/
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Central application configuration.

    Attributes are populated from environment variables or the ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Telegram ---
    bot_token: str = Field(..., description="Telegram Bot API token")
    super_admin_ids: str = Field(
        default="",
        description="Comma-separated Telegram user IDs of initial super admins",
    )

    # --- PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "taskbot"
    postgres_password: str = "taskbot_secret"
    postgres_db: str = "taskbot"
    database_url: str | None = None

    # --- Redis ---
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # --- Application ---
    app_env: str = "development"
    app_timezone: str = "Asia/Tashkent"
    log_level: str = "INFO"
    default_language: str = "uz"

    # --- Working hours ---
    working_hours_start: str = "09:00"
    working_hours_end: str = "18:00"

    # --- Scheduler ---
    scheduler_timezone: str = "Asia/Tashkent"

    # --- Webhook (for deployment on free platforms / servers with HTTPS) ---
    # When USE_WEBHOOK=true, the bot runs in webhook mode instead of long-polling.
    use_webhook: bool = False
    webhook_url: str = ""  # Full public HTTPS URL, e.g. https://mybot.example.com/webhook
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8443
    webhook_path: str = "/webhook"
    # Optional path for a simple health-check endpoint (GET returns 200 OK).
    healthcheck_path: str = "/health"

    # ------------------------------------------------------------------ #
    # Computed / derived values
    # ------------------------------------------------------------------ #
    @computed_field  # type: ignore[misc]
    @property
    def is_production(self) -> bool:
        """Return True when running in production environment."""
        return self.app_env.lower() == "production"

    @computed_field  # type: ignore[misc]
    @property
    def sqlalchemy_database_url(self) -> str:
        """Return the async SQLAlchemy database URL."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def redis_url(self) -> str:
        """Return the Redis connection URL."""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def super_admin_id_list(self) -> List[int]:
        """Parse comma-separated super admin IDs into a list of ints."""
        if not self.super_admin_ids:
            return []
        return [
            int(part.strip())
            for part in self.super_admin_ids.split(",")
            if part.strip().isdigit()
        ]

    @property
    def logs_dir(self) -> Path:
        """Return the logs directory path, creating it if needed."""
        path = PROJECT_ROOT / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def exports_dir(self) -> Path:
        """Return the exports directory path, creating it if needed."""
        path = PROJECT_ROOT / "exports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ------------------------------------------------------------------ #
    # Validators
    # ------------------------------------------------------------------ #
    @field_validator("bot_token")
    @classmethod
    def _validate_token(cls, v: str) -> str:
        if not v or ":" not in v:
            raise ValueError("BOT_TOKEN must be a valid Telegram bot token containing ':'")
        return v.strip()

    @field_validator("app_timezone", "scheduler_timezone")
    @classmethod
    def _validate_tz(cls, v: str) -> str:
        import pytz

        if v not in pytz.all_timezones:
            raise ValueError(f"Unknown timezone: {v}")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` singleton."""
    return Settings()  # type: ignore[call-arg]


# Module-level singleton imported across the app.
settings: Settings = get_settings()
