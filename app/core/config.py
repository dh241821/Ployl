from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application configuration derived from environment variables."""

    app_name: str = "Ployl Medical Device Manager"
    environment: Literal["development", "testing", "production"] = "development"
    database_url: str = Field(
        default_factory=lambda: f"sqlite+aiosqlite:///{Path.cwd() / 'ployl.db'}"
    )
    run_migrations_on_startup: bool = True
    scheduler_timezone: str = "Europe/Vienna"
    maintenance_due_window_days: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
