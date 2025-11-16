"""Dashboard and analytics endpoints."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_session
from ..models import Material, Produkt, Reparatur, Wartung
from ..schemas import DashboardChart, DashboardKPI, DashboardResponse, RepairCostTrend

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def dashboard_overview(session: Session = Depends(get_session), user=Depends(get_current_user)) -> DashboardResponse:
    today = date.today()
    due_products = (
        session.query(Produkt)
        .join(Wartung)
        .filter(Wartung.geplantes_datum <= today, Wartung.durchgefuehrt_am.is_(None))
        .distinct()
        .count()
    )
    in_repair = session.query(Produkt).filter(Produkt.status == "in_reparatur").count()
    expired_materials = session.query(Material).filter(Material.verfallsdatum < today).count()
    low_stock_materials = session.query(Material).filter(Material.ist_bestand < Material.soll_bestand).count()
    upcoming = (
        session.query(Wartung)
        .filter(Wartung.geplantes_datum <= today + timedelta(days=30), Wartung.durchgefuehrt_am.is_(None))
        .count()
    )

    product_status_rows = session.query(Produkt.status, func.count(Produkt.id)).group_by(Produkt.status).all()
    status_chart = DashboardChart(labels=[row[0] for row in product_status_rows], values=[row[1] for row in product_status_rows])

    repair_rows = (
        session.query(func.strftime("%Y-%m", Reparatur.datum), func.sum(Reparatur.kosten))
        .group_by(func.strftime("%Y-%m", Reparatur.datum))
        .order_by(func.strftime("%Y-%m", Reparatur.datum))
        .limit(12)
        .all()
    )
    repair_chart = DashboardChart(
        labels=[row[0] for row in repair_rows],
        values=[int(row[1] or 0) for row in repair_rows],
    )

    category_rows = (
        session.query(Produkt.status, func.count(Produkt.id))
        .group_by(Produkt.status)
        .all()
    )
    category_chart = DashboardChart(labels=[row[0] for row in category_rows], values=[row[1] for row in category_rows])

    repair_trends = [RepairCostTrend(month=row[0], total_cost=float(row[1] or 0.0)) for row in repair_rows]

    return DashboardResponse(
        kpis=DashboardKPI(
            due_products=due_products,
            in_repair=in_repair,
            expired_materials=expired_materials,
            low_stock_materials=low_stock_materials,
            maintenance_due_within_30_days=upcoming,
        ),
        product_status_chart=status_chart,
        category_cost_chart=category_chart,
        repair_frequency_chart=DashboardChart(
            labels=[trend.month for trend in repair_trends],
            values=[int(trend.total_cost) for trend in repair_trends],
        ),
    )
