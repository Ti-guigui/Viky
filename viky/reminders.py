"""Rappels et minuteurs, enregistrés sur le disque pour survivre à un redémarrage."""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from .numbers import parse_number
from .text import fold, normalize

_UNITS = {
    "seconde": 1, "secondes": 1, "second": 1, "seconds": 1,
    "minute": 60, "minutes": 60, "min": 60,
    "heure": 3600, "heures": 3600, "h": 3600, "hour": 3600, "hours": 3600,
}
_NUMBER_WORDS = (
    "un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize|"
    "vingt|trente|quarante|cinquante|soixante|et|one|two|three|four|five|six|seven|eight|nine|ten|"
    "eleven|twelve|fifteen|twenty|thirty|forty|fifty|a|an"
)
_NUM = rf"(?:\d+|(?:(?:{_NUMBER_WORDS}) ?)+)"
_UNIT = r"(?:secondes?|seconds?|minutes?|min|heures?|hours?|h)"
# « dans 10 minutes », « dans une heure et demie », « in 5 minutes »
_IN = re.compile(rf"\b(?:dans|in|pendant|for) (?P<dur>(?:{_NUM}|une demi|un quart d|half an) ?{_UNIT}"
                 rf"(?: et (?:demie?|quart)| and a half)?(?: {_NUM} ?(?:minutes?|min)?)?)")
# « à 18h », « demain à dix huit heures trente », « at 6 pm », « à midi »
_AT = re.compile(rf"(?:\b(?:demain|tomorrow) )?\b(?:a|vers|at) (?:midi|minuit|noon|midnight|"
                 rf"{_NUM} ?(?:h|heures?|o clock)(?: ?{_NUM})?|\d{{1,2}}(?: \d{{2}})?(?: ?(?:am|pm))?)"
                 rf"(?: (?:demain|tomorrow|du soir|du matin))?\b")
_LEADING = re.compile(r"^(?:de|d|qu|que|pour|a|to|that|about)\s+")


@dataclass
class Reminder:
    id: str
    due: float  # horodatage
    text: str
    kind: str = "rappel"  # « rappel » ou « minuteur »

    @property
    def when(self) -> datetime:
        return datetime.fromtimestamp(self.due)


def _number_before(words: list[str], index: int) -> float | None:
    """Le nombre écrit juste avant words[index] (« dix sept minutes » -> 17)."""
    for size in range(min(index, 5), 0, -1):
        value = parse_number(" ".join(words[index - size:index]))
        if value is not None:
            return value
    if words[max(0, index - 2):index] == ["half", "an"]:
        return 0.5
    if index and words[index - 1] in ("demi", "demie", "half"):
        return 0.5
    if index and words[index - 1] in ("a", "an"):
        return 1
    return None


def parse_duration(text: str) -> int | None:
    """« 10 minutes », « une heure et demie », « 1 h 30 », « 90 secondes » -> secondes."""
    words = normalize(text).split()
    total, found = 0.0, False
    for i, word in enumerate(words):
        if word not in _UNITS:
            continue
        number = _number_before(words, i)
        if number is None:
            continue
        unit = _UNITS[word]
        total += number * unit
        found = True
        following = words[i + 1:i + 3]
        if following in (["et", "demie"], ["et", "demi"], ["and", "a"]):
            total += unit / 2
        elif following == ["et", "quart"]:
            total += unit / 4
        elif unit == 3600 and len(words) > i + 1:
            # « 1 h 30 » : les minutes suivent l'heure sans unité
            rest = words[i + 1:]
            minutes = parse_number(" ".join(rest[:2])) if rest[0] not in ("et", "and") else None
            if minutes is not None and not any(w in _UNITS for w in rest[:3]):
                total += minutes * 60
    return int(total) if found and total > 0 else None


def parse_clock(text: str, now: datetime) -> datetime | None:
    """« à 18h », « à dix huit heures trente », « demain à midi », « at 6 pm » -> date et heure."""
    text = normalize(text)
    tomorrow = bool(re.search(r"\b(demain|tomorrow)\b", text))
    day = now.date() + timedelta(days=1) if tomorrow else now.date()
    clean = re.sub(r"\b(demain|tomorrow|a|vers|at|du soir|du matin|o clock)\b", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    if re.search(r"\b(midi|noon)\b", clean):
        hour, minute = 12, 0
    elif re.search(r"\b(minuit|midnight)\b", clean):
        hour, minute = 0, 0
    else:
        pm = bool(re.search(r"\bpm\b", clean)) or "du soir" in text
        clean = re.sub(r"\b(am|pm)\b", "", clean).strip()
        match = re.fullmatch(r"(.+?)(?:(?<=\d)h| (?:h|heures?))(?![a-z])(?: ?(.+))?", clean) or re.fullmatch(r"(\d{1,2})(?: (\d{2}))?", clean)
        if not match:
            return None
        hour = parse_number(match.group(1))
        minute = parse_number(match.group(2)) if match.group(2) else 0
        if hour is None or minute is None:
            return None
        if pm and hour < 12:
            hour += 12
    if hour > 23 or minute > 59:
        return None
    moment = datetime.combine(day, datetime.min.time()).replace(hour=int(hour), minute=int(minute))
    if moment <= now and not tomorrow:
        moment += timedelta(days=1)
    return moment


def parse_reminder(text: str, now: datetime) -> tuple[datetime | None, str]:
    """« d'appeler Paul à 18h » -> (aujourd'hui 18:00, « appeler Paul »)."""
    folded, display = fold(text)
    due = None
    match = _IN.search(folded)
    if match:
        seconds = parse_duration(match.group("dur"))
        due = now + timedelta(seconds=seconds) if seconds else None
    else:
        match = _AT.search(folded)
        if match:
            due = parse_clock(match.group(0), now)
    if match is None:
        what = display.strip()
    else:
        what = (display[:match.start()] + " " + display[match.end():]).strip()
    what = re.sub(r"\s+", " ", what)
    while True:
        cleaned = _LEADING.sub("", what)
        if cleaned == what:
            break
        what = cleaned
    return (due if match else None), what


class Reminders:
    """Garde la liste des rappels et appelle `on_due(rappel)` au bon moment."""

    def __init__(self, path: Path, on_due: Callable[[Reminder], None] | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self.path = path
        self.on_due = on_due
        self.clock = clock
        self.items: list[Reminder] = []
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        try:
            self.items = [Reminder(**r) for r in json.loads(self.path.read_text(encoding="utf-8"))]
        except (OSError, ValueError, TypeError):
            self.items = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(r) for r in self.items], ensure_ascii=False, indent=1),
                             encoding="utf-8")

    def add(self, due: float, text: str, kind: str = "rappel") -> Reminder:
        reminder = Reminder(uuid.uuid4().hex[:8], due, text, kind)
        with self._lock:
            self.items.append(reminder)
            self.items.sort(key=lambda r: r.due)
            self._save()
        return reminder

    def upcoming(self) -> list[Reminder]:
        return [r for r in self.items if r.due > self.clock()]

    def today(self, now: datetime | None = None) -> list[Reminder]:
        now = now or datetime.fromtimestamp(self.clock())
        return [r for r in self.upcoming() if r.when.date() == now.date()]

    def clear(self) -> int:
        with self._lock:
            count = len(self.items)
            self.items = []
            self._save()
        return count

    def pop_due(self) -> list[Reminder]:
        """Retire et renvoie les rappels arrivés à échéance."""
        now = self.clock()
        with self._lock:
            due = [r for r in self.items if r.due <= now]
            if due:
                self.items = [r for r in self.items if r.due > now]
                self._save()
        return due

    def start(self) -> None:
        def loop() -> None:
            while True:
                for reminder in self.pop_due():
                    if self.on_due:
                        try:
                            self.on_due(reminder)
                        except Exception as error:
                            print(f"[Viky] Erreur de rappel : {error}")
                time.sleep(1)

        threading.Thread(target=loop, daemon=True, name="rappels").start()
