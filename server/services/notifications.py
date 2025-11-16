"""Notification and reminder utilities."""
from __future__ import annotations

from datetime import date, timedelta
from email.message import EmailMessage
from typing import Iterable, List

from ics import Calendar, Event
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Benutzer, Produkt, Wartung
from ..schemas import MaintenanceReminder, NotificationResult

try:  # optional dependency for SMTP sending
    import aiosmtplib
except Exception:  # pragma: no cover - optional runtime dependency
    aiosmtplib = None


class NotificationService:
    """Create reminder payloads and optionally dispatch them via email."""

    def __init__(self, session: Session):
        self.session = session

    def fetch_due_wartungen(self, within_days: int = 30) -> List[MaintenanceReminder]:
        today = date.today()
        limit = today + timedelta(days=within_days)
        reminders: List[MaintenanceReminder] = []
        wartungen = (
            self.session.query(Wartung)
            .join(Produkt)
            .filter(Wartung.geplantes_datum <= limit, Wartung.durchgefuehrt_am.is_(None))
            .all()
        )
        for wartung in wartungen:
            reminders.append(
                MaintenanceReminder(
                    produkt_id=wartung.produkt_id,
                    produkt_name=wartung.produkt.name,
                    due_date=wartung.geplantes_datum,
                    typ=wartung.typ,
                )
            )
        return reminders

    def build_calendar(self, reminders: Iterable[MaintenanceReminder]) -> Calendar:
        calendar = Calendar()
        for reminder in reminders:
            event = Event()
            event.name = f"Wartung: {reminder.produkt_name}"
            event.begin = reminder.due_date
            event.duration = timedelta(hours=1)
            event.description = f"{reminder.typ} für {reminder.produkt_name}"
            calendar.events.add(event)
        return calendar

    async def send_email(self, recipients: Iterable[str], reminders: List[MaintenanceReminder]) -> NotificationResult:
        if not settings.smtp_host or not settings.smtp_sender:
            return NotificationResult(recipients=[], reminders=reminders)
        if not reminders:
            return NotificationResult(recipients=list(recipients), reminders=reminders)
        if aiosmtplib is None:  # pragma: no cover
            raise RuntimeError("aiosmtplib is required for email notifications")
        calendar = self.build_calendar(reminders)
        message = EmailMessage()
        message["From"] = settings.smtp_sender
        message["To"] = ",".join(recipients)
        message["Subject"] = "Wartungserinnerung"
        body_lines = ["Folgende Wartungen stehen an:"]
        for reminder in reminders:
            body_lines.append(f"- {reminder.produkt_name} am {reminder.due_date:%d.%m.%Y} ({reminder.typ})")
        message.set_content("\n".join(body_lines))
        message.add_attachment(
            str(calendar),
            maintype="text",
            subtype="calendar",
            filename="wartungen.ics",
        )
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            start_tls=True,
        )
        return NotificationResult(recipients=list(recipients), reminders=reminders)

    def send_notifications_for_admins(self, within_days: int = 30) -> NotificationResult:
        reminders = self.fetch_due_wartungen(within_days=within_days)
        admins = [user.email for user in self.session.query(Benutzer).filter(Benutzer.role == "admin").all() if user.email]
        return NotificationResult(recipients=admins, reminders=reminders)


__all__ = ["NotificationService"]
