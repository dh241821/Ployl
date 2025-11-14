"""Configuration utilities for the FastAPI backend."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic import BaseSettings, EmailStr, Field, validator


class Settings(BaseSettings):
    """Environment driven configuration for the backend services."""

    app_name: str = "Medizinprodukte Management API"
    secret_key: str = Field(..., env="APP_SECRET_KEY")
    access_token_expire_minutes: int = 60 * 12
    database_url: str = Field(
        default="sqlite:///./medizinprodukte_network.db",
        env="DATABASE_URL",
    )
    smtp_host: Optional[str] = Field(default=None, env="SMTP_HOST")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_username: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    smtp_sender: Optional[EmailStr] = Field(default=None, env="SMTP_SENDER")
    dashboard_cache_seconds: int = 60
    audit_secret: str = Field(default="audit-secret-key", env="AUDIT_SECRET")
    cloud_storage_base_url: Optional[str] = Field(default=None, env="CLOUD_STORAGE_BASE_URL")
    ocr_languages: str = Field(default="deu+eng", env="OCR_LANGUAGES")
    geo_route_profile: str = Field(default="driving", env="GEO_ROUTE_PROFILE")
    maintenance_model_version: str = Field(default="1.0.0", env="MAINTENANCE_MODEL_VERSION")
    encryption_key: Optional[str] = Field(default=None, env="ENCRYPTION_KEY")
    mfa_issuer: str = Field(default="Medizinprodukte", env="MFA_ISSUER")
    sso_client_id: Optional[str] = Field(default=None, env="SSO_CLIENT_ID")
    sso_client_secret: Optional[str] = Field(default=None, env="SSO_CLIENT_SECRET")
    blockchain_salt: str = Field(default="med-chain", env="BLOCKCHAIN_SALT")
    offline_cache_dir: str = Field(default="storage/offline", env="OFFLINE_CACHE_DIR")
    iot_temperature_threshold: float = Field(default=8.0, env="IOT_TEMPERATURE_THRESHOLD")
    iot_humidity_threshold: float = Field(default=70.0, env="IOT_HUMIDITY_THRESHOLD")
    prediction_horizon_days: int = Field(default=30, env="PREDICTION_HORIZON_DAYS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("database_url")
    def ensure_driver(cls, value: str) -> str:  # noqa: D401
        """Ensure the SQLAlchemy URL contains an explicit driver."""

        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://") and "+" not in value:
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        if value.startswith("mysql://"):
            return value.replace("mysql://", "mysql+pymysql://", 1)
        return value


@lru_cache()
def get_settings() -> Settings:
    """Return a cached instance of :class:`Settings`."""

    secret = os.getenv("APP_SECRET_KEY")
    if not secret:
        # provide deterministic fallback for development to keep runtime simple
        os.environ.setdefault("APP_SECRET_KEY", "development-secret-key")
    return Settings()


settings = get_settings()
