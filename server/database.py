"""SQLAlchemy session and metadata helpers for the network backend."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, scoped_session, sessionmaker

from .config import settings

Base = declarative_base()

_engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
_SessionFactory = scoped_session(sessionmaker(bind=_engine, expire_on_commit=False, autoflush=False))


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""

    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Session:
    """Return a SQLAlchemy session (FastAPI dependency friendly)."""

    return _SessionFactory()
