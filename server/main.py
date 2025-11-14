"""FastAPI entry-point for the Medizinprodukte Management network backend."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, _engine, session_scope
from .auth import hash_password
from .routers import auth as auth_router
from .routers import dashboard as dashboard_router
from .routers import notifications as notifications_router
from .routers import scanner as scanner_router
from .services.scheduler import register_scheduler

Base.metadata.create_all(bind=_engine)

with session_scope() as session:
    from .models import Benutzer

    if not session.query(Benutzer).filter(Benutzer.username == "admin").first():
        session.add(
            Benutzer(
                username="admin",
                full_name="Administrator",
                role="admin",
                password_hash=hash_password("admin"),
            )
        )
        session.commit()

app = FastAPI(title=settings.app_name)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(scanner_router.router)
app.include_router(notifications_router.router)

register_scheduler(app)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    html_file = static_dir / "index.html"
    return HTMLResponse(html_file.read_text(encoding="utf-8"))
