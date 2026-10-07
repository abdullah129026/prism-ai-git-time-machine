"""PRISM backend configuration — environment-driven, typed via pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PRISM_", env_file=".env", extra="ignore")

    app_name: str = "PRISM API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Comma-separated origins for CORS; "*" only for local dev.
    cors_origins: str = "http://localhost:3000"

    # Where cloned repos and job state live.
    data_dir: Path = Path("/tmp/prism_data")

    # Ingest limits.
    max_commits: int = 2000
    clone_timeout_seconds: int = 300

    # Downstream services.
    groq_api_key: str = ""
    qdrant_url: str = "http://localhost:6333"

    # Pre-loaded demo repo, ingested once on startup. Empty disables it.
    demo_repo: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
