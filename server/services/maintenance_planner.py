"""Automated maintenance planning powered by simple ML heuristics."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, Iterable, List, Tuple

import numpy as np
from sklearn.linear_model import LinearRegression
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Produkt, Wartung, WartungsInsight


class MaintenancePlanner:
    """Generate predictive maintenance insights for products."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def refresh_insights(self) -> List[WartungsInsight]:
        """Rebuild the insight table and return current predictions."""

        insights: List[WartungsInsight] = []
        # clear previous predictions to avoid stale rows
        self.session.query(WartungsInsight).delete()
        self.session.flush()

        datasets = self._build_datasets()
        today = date.today()

        for produkt_id, (produkt, durations) in datasets.items():
            if not durations:
                continue
            predicted_days, confidence, data_points, method = self._predict_days(durations)

            if produkt.letzte_stk:
                basis = produkt.letzte_stk
            elif produkt.letzte_mtk:
                basis = produkt.letzte_mtk
            elif produkt.anschaffungsdatum:
                basis = produkt.anschaffungsdatum
            else:
                basis = today

            prognose_datum = basis + timedelta(days=int(round(predicted_days)))
            if prognose_datum < today:
                prognose_datum = today + timedelta(days=produkt.stk_intervall * 30 if produkt.stk_intervall else 30)

            fenster_start = prognose_datum - timedelta(days=7)
            fenster_ende = prognose_datum + timedelta(days=7)

            insight = WartungsInsight(
                produkt_id=produkt_id,
                modell_version=settings.maintenance_model_version,
                prognose_datum=prognose_datum,
                fenster_start=fenster_start,
                fenster_ende=fenster_ende,
                konfidens=confidence,
                datenpunkte=data_points,
                methode=method,
                metadaten=str({"durations": durations}),
            )
            self.session.add(insight)
            insights.append(insight)

        self.session.flush()
        return insights

    def _build_datasets(self) -> Dict[int, Tuple[Produkt, List[int]]]:
        """Collect historical maintenance durations per product."""

        maintenance_rows = (
            self.session.query(Wartung)
            .filter(Wartung.durchgefuehrt_am.isnot(None))
            .order_by(Wartung.produkt_id, Wartung.durchgefuehrt_am)
            .all()
        )

        grouped: Dict[int, List[date]] = defaultdict(list)
        for row in maintenance_rows:
            grouped[row.produkt_id].append(row.durchgefuehrt_am)

        produkt_map = {produkt.id: produkt for produkt in self.session.query(Produkt).all()}
        datasets: Dict[int, Tuple[Produkt, List[int]]] = {}

        for produkt_id, produkt in produkt_map.items():
            completions = grouped.get(produkt_id, [])
            durations = self._durations_for_product(produkt, completions)
            datasets[produkt_id] = (produkt, durations)

        return datasets

    def _durations_for_product(self, produkt: Produkt, completions: Iterable[date]) -> List[int]:
        """Return maintenance durations in days for a product."""

        completions = list(sorted(completions))
        durations: List[int] = []

        if not completions:
            if produkt.stk_intervall:
                durations.append(int(produkt.stk_intervall * 30))
            elif produkt.mtk_intervall:
                durations.append(int(produkt.mtk_intervall * 30))
            else:
                durations.append(180)
            return durations

        previous = completions[0]
        for current in completions[1:]:
            durations.append((current - previous).days or 1)
            previous = current

        if not durations:
            # only a single completion -> infer from intervals
            if produkt.stk_intervall:
                durations.append(int(produkt.stk_intervall * 30))
            elif produkt.mtk_intervall:
                durations.append(int(produkt.mtk_intervall * 30))
            else:
                durations.append(180)

        return durations

    def _predict_days(self, durations: List[int]) -> Tuple[float, float, int, str]:
        """Predict the next maintenance interval in days."""

        data_points = len(durations)
        method = "linear_regression"

        if data_points >= 2:
            x = np.arange(data_points).reshape(-1, 1)
            y = np.array(durations, dtype=float)
            model = LinearRegression()
            model.fit(x, y)
            prediction = float(model.predict([[data_points]])[0])
            score = model.score(x, y)
            confidence = float(max(0.35, min(0.95, score if score > 0 else 0.4)))
            if prediction <= 0:
                prediction = float(np.mean(y))
                method = "mean_fallback"
        else:
            prediction = float(durations[-1])
            confidence = 0.4
            method = "historical_default"

        # guard rails to avoid unrealistic predictions
        prediction = max(30.0, min(prediction, 540.0))
        return prediction, confidence, data_points, method
