"""AI-assisted helpers including chatbot, categorisation and anomaly scoring."""
from __future__ import annotations

import statistics
from typing import List, Tuple

from sqlalchemy.orm import Session

from ..models import AnomalyEvent, CategorizationSuggestion, ChatConversation


class AIService:
    """Simple rule and statistics based AI helpers."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # chatbot
    # ------------------------------------------------------------------
    def chat(self, prompt: str, context: str | None = None) -> Tuple[str, str | None, float]:
        lowered = prompt.lower()
        intent = None
        confidence = 0.6
        if "wartung" in lowered or "maintenance" in lowered:
            intent = "maintenance"
            response = (
                "Geplante Wartungen findest du im Wartungs-Report. "
                "Nutze den PWA-Offline-Modus, um direkt vor Ort zu protokollieren."
            )
            confidence = 0.85
        elif "reparatur" in lowered or "repair" in lowered:
            intent = "repair"
            response = (
                "Dokumentiere Reparaturen über den Dialog 'Reparaturen verwalten'. "
                "Alle Kosten werden automatisch in den Lebenszyklus übernommen."
            )
            confidence = 0.8
        elif "bestellung" in lowered or "order" in lowered:
            intent = "procurement"
            response = (
                "Die ERP-Integration erstellt Bestellvorschläge für Materialien mit niedrigem Bestand. "
                "Prüfe den Abschnitt 'Bestellliste'."
            )
            confidence = 0.75
        else:
            response = (
                "Ich habe deine Frage gespeichert. Bitte prüfe die Dokumentation im Hilfe-Tab "
                "oder kontaktiere das Technikteam."
            )
            confidence = 0.55

        conversation = ChatConversation(prompt=prompt, response=response, intent=intent, confidence=confidence)
        self.session.add(conversation)
        self.session.commit()
        return response, intent, confidence

    # ------------------------------------------------------------------
    # categorisation
    # ------------------------------------------------------------------
    def categorise(self, name: str, beschreibung: str | None = None, produkt_id: int | None = None) -> Tuple[str, float, str]:
        tokens = (beschreibung or "").lower() + " " + name.lower()
        suggestions = {
            "Defibrillator": ["defib", "aed", "herz"],
            "Beatmungsgerät": ["resp", "vent", "beatmung"],
            "Verbandsmaterial": ["verband", "pflaster", "binde"],
            "Medikament": ["ampulle", "tablette", "medizin"],
            "Monitoring": ["monitor", "überwachung", "monitoring"],
        }
        best_match = "Sonstiges"
        best_score = 0
        rationale = "Keine Schlüsselwörter gefunden"
        for label, keywords in suggestions.items():
            matches = sum(1 for keyword in keywords if keyword in tokens)
            if matches > best_score:
                best_score = matches
                best_match = label
                rationale = f"Gefundene Schlüsselwörter: {', '.join([k for k in keywords if k in tokens])}"
        confidence = min(0.3 + 0.2 * best_score, 0.95)
        if produkt_id:
            suggestion = CategorizationSuggestion(
                produkt_id=produkt_id,
                suggested_kategorie=best_match,
                confidence=confidence,
                rationale=rationale,
            )
            self.session.add(suggestion)
            self.session.commit()
        return best_match, confidence, rationale

    # ------------------------------------------------------------------
    # anomaly detection
    # ------------------------------------------------------------------
    def detect_anomaly(self, values: List[float], metric: str, scope: str, reference_id: int | None) -> Tuple[bool, float, float, str]:
        if not values:
            return False, 0.0, 0.0, "Keine Daten"
        mean = statistics.fmean(values)
        std = statistics.pstdev(values) or 1.0
        latest = values[-1]
        score = abs(latest - mean) / std
        threshold = 3.0
        anomaly = score > threshold
        details = f"letzter Wert {latest:.2f}, Mittelwert {mean:.2f}, σ {std:.2f}"
        event = AnomalyEvent(scope=scope, reference_id=reference_id, metric=metric, score=score, details=details)
        self.session.add(event)
        self.session.commit()
        return anomaly, score, threshold, details

