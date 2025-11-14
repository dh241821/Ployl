"""FastAPI entry-point for the Medizinprodukte Management network backend."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, _engine, session_scope
from .auth import hash_password
from .models import Benutzer, Dokument, Fahrzeug, FahrzeugPosition, Kostenbuchung, Material, Produkt, Reparatur, Wartung, WartungsInsight
from .routers import auth as auth_router
from .routers import dashboard as dashboard_router
from .routers import notifications as notifications_router
from .routers import scanner as scanner_router
from .routers import maintenance as maintenance_router
from .routers import costs as costs_router
from .routers import documents as documents_router
from .routers import geotracking as geotracking_router
from .routers import audit as audit_router
from .routers import integrations as integrations_router
from .routers import ai as ai_router
from .routers import security as security_router
from .routers import iot as iot_router
from .routers import offline as offline_router
from .routers import blockchain as blockchain_router
from .routers import predictions as predictions_router
from .routers import ar as ar_router
from .services.audit import configure_audit_events
from .services.scheduler import register_scheduler

Base.metadata.create_all(bind=_engine)

with session_scope() as session:
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

configure_audit_events(
    (
        Benutzer,
        Produkt,
        Fahrzeug,
        Material,
        Reparatur,
        Wartung,
        Dokument,
        Kostenbuchung,
        WartungsInsight,
        FahrzeugPosition,
    )
)

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(scanner_router.router)
app.include_router(notifications_router.router)
app.include_router(maintenance_router.router)
app.include_router(costs_router.router)
app.include_router(documents_router.router)
app.include_router(geotracking_router.router)
app.include_router(audit_router.router)
app.include_router(integrations_router.router)
app.include_router(ai_router.router)
app.include_router(security_router.router)
app.include_router(iot_router.router)
app.include_router(offline_router.router)
app.include_router(blockchain_router.router)
app.include_router(predictions_router.router)
app.include_router(ar_router.router)

register_scheduler(app)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    html_file = static_dir / "index.html"
    return HTMLResponse(html_file.read_text(encoding="utf-8"))
