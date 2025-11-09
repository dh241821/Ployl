from functools import lru_cache
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application configuration."""

    app_name: str = Field(default="Ployl Incident Manager", description="Human readable application name")
    database_url: str = Field(default="sqlite+aiosqlite:///./plosl.db", description="SQLAlchemy database URL")
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost", "http://localhost:5173"], description="CORS origins")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
