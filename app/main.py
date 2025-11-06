from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import assignments, checks, device_types, devices, maintenance, repairs, vehicles
from .core.config import get_settings
from .database import AsyncSessionFactory, engine
from .services.scheduler import configure_scheduler
from .utils.migrations import run_migrations

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.run_migrations_on_startup:
        await run_migrations(engine)
        logger.info("Database migrations executed")

    scheduler = None
    if settings.environment != "testing":
        scheduler = configure_scheduler()
        scheduler.start()
        logger.info("Maintenance scheduler started")

    try:
        yield
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
        await AsyncSessionFactory.close_all()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.include_router(vehicles.router)
    app.include_router(device_types.router)
    app.include_router(devices.router)
    app.include_router(assignments.router)
    app.include_router(checks.router)
    app.include_router(repairs.router)
    app.include_router(maintenance.router)

    return app


app = create_app()


__all__ = ["app", "create_app"]
