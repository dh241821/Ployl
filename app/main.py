from __future__ import annotations

from contextlib import asynccontextmanager

from app.core.compat import patch_forward_ref_evaluate

patch_forward_ref_evaluate()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import incidents, patients, personnel, vehicles, hospitals
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


settings = get_settings()

app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vehicles.router)
app.include_router(incidents.router)
app.include_router(hospitals.router)
app.include_router(personnel.router)
app.include_router(patients.router)


@app.get("/")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
