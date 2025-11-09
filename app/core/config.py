from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal, cast

ENV_FILE = Path.cwd() / ".env"


def _load_env_file(path: Path) -> None:
    """Populate ``os.environ`` with variables from a classic ``.env`` file."""

    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        key, sep, value = line.partition("=")
        if not sep:
            continue

        key = key.strip()
        if not key or key in os.environ:
            continue

        value = value.strip()
        if value and ((value[0] == value[-1]) and value.startswith(("'", '"'))):
            value = value[1:-1]

        os.environ.setdefault(key, value)


_load_env_file(ENV_FILE)


def _coerce_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default

    truthy = {"1", "true", "t", "yes", "y", "on"}
    falsy = {"0", "false", "f", "no", "n", "off"}
    normalised = value.strip().lower()

    if normalised in truthy:
        return True
    if normalised in falsy:
        return False
    return default


def _coerce_int(value: str | None, default: int) -> int:
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Application configuration derived from environment variables."""

    app_name: str
    environment: Literal["development", "testing", "production"]
    database_url: str
    run_migrations_on_startup: bool
    scheduler_timezone: str
    maintenance_due_window_days: int
    upload_dir: Path

    @classmethod
    def load(cls) -> "Settings":
        default_db = f"sqlite+aiosqlite:///{Path.cwd() / 'ployl.db'}"
        env = os.environ

        environment = env.get("ENVIRONMENT", "development").lower()
        if environment not in {"development", "testing", "production"}:
            environment = "development"

        upload_root = Path(env.get("UPLOAD_DIR", Path.cwd() / "uploads")).resolve()
        upload_root.mkdir(parents=True, exist_ok=True)

        return cls(
            app_name=env.get("APP_NAME", "Ployl Medical Device Manager"),
            environment=cast(Literal["development", "testing", "production"], environment),
            database_url=env.get("DATABASE_URL", default_db),
            run_migrations_on_startup=_coerce_bool(
                env.get("RUN_MIGRATIONS_ON_STARTUP"), True
            ),
            scheduler_timezone=env.get("SCHEDULER_TIMEZONE", "Europe/Vienna"),
            maintenance_due_window_days=_coerce_int(
                env.get("MAINTENANCE_DUE_WINDOW_DAYS"), 30
            ),
            upload_dir=upload_root,
        )


@lru_cache()
def get_settings() -> Settings:
    return Settings.load()


__all__ = ["Settings", "get_settings"]
