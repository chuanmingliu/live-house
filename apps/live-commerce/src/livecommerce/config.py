from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    The default configuration is deliberately local-first and uses the mock generation
    gateway. Production should set FAL_MODE=queue and expose PUBLIC_BASE_URL over HTTPS.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    database_path: str = "./data/live-commerce.db"
    public_base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:8000"

    fal_mode: Literal["mock", "queue"] = "mock"
    fal_key: str | None = None
    fal_model_id: str | None = None
    fal_verify_webhooks: bool = True
    fal_jwks_url: str = "https://rest.fal.ai/.well-known/jwks.json"
    fal_webhook_path: str = "/v1/webhooks/fal"
    fal_job_deadline_seconds: int = 90

    mock_generation_delay_seconds: float = 1.0
    mock_asset_url: str = "/static/demo-segment.mp4"

    event_replay_limit: int = 250
    auto_seed_products: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def webhook_url(self) -> str:
        return f"{self.public_base_url.rstrip('/')}/{self.fal_webhook_path.lstrip('/')}"

    @property
    def resolved_database_path(self) -> Path:
        path = Path(self.database_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    def validate_fal_configuration(self) -> None:
        if self.fal_mode != "queue":
            return
        missing: list[str] = []
        if not self.fal_key:
            missing.append("FAL_KEY")
        if not self.fal_model_id:
            missing.append("FAL_MODEL_ID")
        if missing:
            raise RuntimeError(f"fal queue mode requires: {', '.join(missing)}")
        if not self.public_base_url.startswith("https://") and self.app_env == "production":
            raise RuntimeError("PUBLIC_BASE_URL must use HTTPS in production")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
