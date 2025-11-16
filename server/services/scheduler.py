"""Background scheduler that dispatches maintenance notifications."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from ..database import session_scope
from ..services.notifications import NotificationService


class SchedulerManager:
    """Manage an APScheduler instance tied to the FastAPI lifespan."""

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone="Europe/Vienna")

    def start(self) -> None:
        if self.scheduler.running:
            return
        self.scheduler.start()
        self.scheduler.add_job(self._dispatch_notifications, "cron", hour=6)

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown()

    async def _dispatch_notifications(self) -> None:
        with session_scope() as session:
            service = NotificationService(session)
            service.send_notifications_for_admins()


scheduler_manager = SchedulerManager()


def register_scheduler(app: FastAPI) -> None:
    @app.on_event("startup")
    async def _start() -> None:  # pragma: no cover - FastAPI lifecycle
        scheduler_manager.start()

    @app.on_event("shutdown")
    async def _stop() -> None:  # pragma: no cover - FastAPI lifecycle
        scheduler_manager.shutdown()
