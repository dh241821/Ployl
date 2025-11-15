"""Application-wide configuration helpers."""

from __future__ import annotations

from pathlib import Path

_DEFAULT_DB_PATH = Path("medizinprodukte.db")


def get_db_path() -> Path:
    """Return the default SQLite database path."""

    return _DEFAULT_DB_PATH


__all__ = ["get_db_path"]
