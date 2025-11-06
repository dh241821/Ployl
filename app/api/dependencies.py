from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session


async def get_db_session(session: AsyncSession = Depends(get_session)) -> AsyncSession:
    return session


__all__ = ["get_db_session"]
