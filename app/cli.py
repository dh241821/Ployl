from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .core.config import get_settings
from .database import AsyncSessionFactory, engine
from .services.device_service import get_upcoming_maintenance
from .utils.migrations import run_migrations

app = typer.Typer(help="Management commands for the Ployl backend")
console = Console()


@app.command()
def migrate() -> None:
    """Create database schema."""

    async def _migrate() -> None:
        await run_migrations(engine)

    asyncio.run(_migrate())
    console.print("[green]Migrations completed[/green]")


@app.command()
def upcoming(days: Optional[int] = typer.Option(None, help="Lookahead window in days")) -> None:
    """Show upcoming MTK/STK checks."""

    async def _show() -> None:
        async with AsyncSessionFactory() as session:
            windows = await get_upcoming_maintenance(session, days)
        if not windows:
            console.print("[yellow]No upcoming checks in window[/yellow]")
            return
        table = Table(title="Upcoming Maintenance")
        table.add_column("Device")
        table.add_column("Check")
        table.add_column("Due On")
        table.add_column("Days")
        for window in windows:
            table.add_row(
                window.device_inventory_number,
                window.check_type,
                window.due_on.isoformat(),
                str(window.days_until_due),
            )
        console.print(table)

    asyncio.run(_show())


@app.command()
def settings() -> None:
    """Display effective configuration."""

    cfg = get_settings()
    table = Table(title="Settings")
    for field, value in cfg.dict().items():
        table.add_row(field, str(value))
    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
