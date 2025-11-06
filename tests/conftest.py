from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient

# Configure environment before importing app modules
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("RUN_MIGRATIONS_ON_STARTUP", "False")

tmp_db_path = os.environ.get("TEST_DB_PATH")
if not tmp_db_path:
    tmp_db_path = os.path.join(os.getcwd(), "test.db")
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_db_path}"

from app.core.config import get_settings
from app.database import AsyncSessionFactory, engine
from app.main import create_app
from app.utils.migrations import run_migrations

get_settings.cache_clear()


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:  # pragma: no cover - pytest hook
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def prepare_database() -> AsyncGenerator[None, None]:
    await run_migrations(engine)
    yield
    if os.path.exists(tmp_db_path):
        os.remove(tmp_db_path)


@pytest.fixture()
async def client() -> AsyncGenerator[AsyncClient, None]:
    app = create_app()
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture()
async def session() -> AsyncGenerator:  # pragma: no cover - helper fixture
    async with AsyncSessionFactory() as session:
        yield session

