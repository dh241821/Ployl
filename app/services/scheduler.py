from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..database import AsyncSessionFactory
from ..services.device_service import get_upcoming_maintenance, sync_maintenance_alerts

logger = logging.getLogger(__name__)


async def maintenance_job() -> None:
    async with AsyncSessionFactory() as session:
        windows = await get_upcoming_maintenance(session)
        alerts = await sync_maintenance_alerts(session, windows)
        await session.commit()
        if not alerts:
            logger.info("Maintenance check completed: no upcoming MTK/STK due soon")
            return
        for alert in alerts:
            logger.warning(
                "Upcoming %s check for device %s due on %s (%s days) [%s]",
                alert.check_type,
                alert.device.inventory_number if alert.device else alert.device_id,
                alert.due_on,
                alert.days_until_due,
                alert.severity,
            )


def configure_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
    scheduler.add_job(
        maintenance_job,
        trigger=IntervalTrigger(hours=12, timezone=settings.scheduler_timezone),
        id="maintenance_reminder",
        replace_existing=True,
        next_run_time=datetime.now(),
    )
    return scheduler


__all__ = ["configure_scheduler", "maintenance_job"]
