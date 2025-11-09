from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from ..database import Base


def _apply_schema_upgrades(connection) -> None:
    """Apply lightweight, idempotent schema upgrades for SQLite deployments."""

    # Ensure new tables are present before adding additional columns.
    Base.metadata.create_all(bind=connection)

    inspector = inspect(connection)
    tables = {table_name.lower() for table_name in inspector.get_table_names()}

    if "device_type" in tables:
        columns = {column["name"] for column in inspector.get_columns("device_type")}
        if "category_id" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE device_type ADD COLUMN category_id INTEGER"
                    " REFERENCES device_category(id)"
                )
            )


async def run_migrations(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(_apply_schema_upgrades)


__all__ = ["run_migrations"]
