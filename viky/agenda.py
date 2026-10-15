"""Agendas Google et iCloud.

- Google Agenda : lecture par l'« adresse secrète au format iCal » de chaque agenda.
- Calendrier iCloud : lecture et ajout de rendez-vous (CalDAV, mot de passe d'application).
Les nouveaux rendez-vous dictés à Viky sont ajoutés au calendrier iCloud,
qui se synchronise avec votre iPhone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .web import get

ICLOUD_CALDAV = "https://caldav.icloud.com"


@dataclass
class Event:
    title: str
    start: datetime
    end: datetime
    all_day: bool = False
    calendar: str = ""


def _local(value) -> tuple[datetime, bool]:
    """Convertit une date iCal en date et heure locales (sans fuseau)."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone().replace(tzinfo=None)
        return value, False
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()), True
    raise TypeError(value)


def events_from_ics(data: bytes | str, start: datetime, end: datetime, calendar: str = "") -> list[Event]:
    """Événements (récurrences comprises) d'un fichier iCal entre deux dates."""
    import icalendar
    import recurring_ical_events

    parsed = icalendar.Calendar.from_ical(data)
    events = []
    for component in recurring_ical_events.of(parsed).between(start, end):
        begin, all_day = _local(component.decoded("DTSTART"))
        try:
            finish, _ = _local(component.decoded("DTEND"))
        except KeyError:
            finish = begin + (timedelta(days=1) if all_day else timedelta(hours=1))
        title = str(component.get("SUMMARY", "")).strip() or "(sans titre)"
        events.append(Event(title, begin, finish, all_day, calendar))
    return events


class Agenda:
    def __init__(self, google_urls: list[str] | None = None, icloud_user: str | None = None,
                 icloud_password: str | None = None, icloud_calendar: str | None = None) -> None:
        self.google_urls = google_urls or []
        self.icloud_user = icloud_user
        self.icloud_password = icloud_password
        self.icloud_calendar = icloud_calendar
        self._calendars = None

    @property
    def configured(self) -> bool:
        return bool(self.google_urls or (self.icloud_user and self.icloud_password))

    @property
    def can_add(self) -> bool:
        return bool(self.icloud_user and self.icloud_password)

    def _icloud_calendars(self):
        if self._calendars is None:
            import caldav

            client = caldav.DAVClient(ICLOUD_CALDAV, username=self.icloud_user, password=self.icloud_password)
            self._calendars = client.principal().calendars()
        return self._calendars

    def events(self, start: datetime, end: datetime) -> list[Event]:
        found: list[Event] = []
        errors = []
        for url in self.google_urls:
            try:
                found += events_from_ics(get(url, timeout=15), start, end, "Google")
            except Exception as error:
                errors.append(error)
        if self.icloud_user and self.icloud_password:
            try:
                for calendar in self._icloud_calendars():
                    for item in calendar.search(start=start, end=end, event=True, expand=True):
                        found += events_from_ics(item.data, start, end, calendar.name or "iCloud")
            except Exception as error:
                errors.append(error)
        if errors and not found:
            raise errors[0]
        unique = {(e.title, e.start): e for e in found}  # un même événement peut venir de deux agendas
        return sorted(unique.values(), key=lambda e: (e.start, e.title))

    def add(self, title: str, start: datetime, duration: timedelta = timedelta(hours=1)) -> str:
        """Ajoute un rendez-vous au calendrier iCloud. Renvoie le nom du calendrier."""
        if not self.can_add:
            raise PermissionError("aucun calendrier iCloud configuré")
        calendars = self._icloud_calendars()
        calendar = next((c for c in calendars if self.icloud_calendar and c.name == self.icloud_calendar),
                        None) or calendars[0]
        calendar.save_event(dtstart=start, dtend=start + duration, summary=title)
        return calendar.name or "iCloud"


def day_range(text: str, now: datetime) -> tuple[datetime, datetime, str]:
    """« aujourd'hui », « demain », « cette semaine », « lundi »… -> (début, fin, libellé)."""
    from .text import normalize

    text = normalize(text)
    today = datetime.combine(now.date(), datetime.min.time())
    days = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    if "apres demain" in text:
        start = today + timedelta(days=2)
        return start, start + timedelta(days=1), "après-demain"
    if "demain" in text or "tomorrow" in text:
        start = today + timedelta(days=1)
        return start, start + timedelta(days=1), "demain"
    if "semaine" in text or ("week" in text and "end" not in text):
        return now, today + timedelta(days=7), "cette semaine"
    if "week end" in text or "weekend" in text:
        start = today + timedelta(days=(5 - today.weekday()) % 7)
        return start, start + timedelta(days=2), "ce week-end"
    for index, name in enumerate(days):
        if name in text.split():
            start = today + timedelta(days=(index - today.weekday()) % 7 or 7)
            return start, start + timedelta(days=1), name
    if "prochain" in text or "next" in text:
        return now, today + timedelta(days=30), "prochain"
    return now, today + timedelta(days=1), "aujourd'hui"
