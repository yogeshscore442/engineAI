"""
config.py — Application settings loaded from .env.
Never log or expose secret values.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # AI Engine
    use_mock_ai: bool = False
    allow_mock_fallback: bool = False
    ai_timeout_seconds: int = 300

    # Database
    database_url: str = f"sqlite:///{(Path(__file__).resolve().parents[1] / 'health_copilot.db').as_posix()}"

    # File Storage
    upload_dir: Path = Path(__file__).resolve().parents[1] / "uploads"
    max_upload_mb: int = 10

    # Feature Flags
    feature_ask: bool = True
    feature_abha_mock: bool = True
    feature_family_profiles: bool = True

    # Security
    secret_key: str = "change-me-in-production"

    # Rate Limiting
    upload_rate_limit: str = "10/minute"

    # Schema / API versioning
    schema_version: int = 1
    api_version: str = "v1"

    # Logging
    log_level: str = "INFO"

    # Computed helpers
    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def upload_dir_resolved(self) -> Path:
        return self.upload_dir.resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
