"""Application-wide configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_DATA_DIR = Path(os.environ.get("MPMS_DATA_DIR", ".")).expanduser()
_DEFAULT_DB_PATH = Path(os.environ.get("MPMS_DB", "medizinprodukte.db"))


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_root() -> Path:
    """Return the root directory that stores app-managed files."""

    return _DEFAULT_DATA_DIR


def get_db_path() -> Path:
    """Return the default SQLite database path."""

    db_path = _DEFAULT_DB_PATH
    if not db_path.is_absolute():
        db_path = get_data_root() / db_path
    return db_path


def get_storage_dir() -> Path:
    """Directory that stores uploaded or generated documents."""

    return _ensure_dir(get_data_root() / "storage")


def get_exports_dir() -> Path:
    """Directory where exports such as CSV/PDF/ICS files are written."""

    return _ensure_dir(get_data_root() / "exports")


def get_docs_dir() -> Path:
    """Directory that contains static documentation artefacts."""

    return _ensure_dir(get_data_root() / "docs")


__all__ = [
    "get_data_root",
    "get_db_path",
    "get_docs_dir",
    "get_exports_dir",
    "get_storage_dir",
]
