from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from ..database import Base


async def run_migrations(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


__all__ = ["run_migrations"]
