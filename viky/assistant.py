"""Le cerveau de Viky : décide quoi faire de chaque phrase entendue."""

from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Callable, Protocol

from . import actions as default_actions
from . import projector as default_projector
from .config import Config
from .files import FileIndex, kind_of
from .intents import Intent, parse_any
from .messages import date_sentence, say, time_sentence
from .numbers import parse_cell, parse_number, parse_value
from .text import normalize, strip_wake_word

_CURRENT_WORDS = {"ca", "cela", "ceci", "la fenetre", "le fichier", "it", "this", "the window"}


class Speaker(Protocol):
    def say(self, text: str, lang: str) -> None: ...


class Assistant:
    def __init__(self, config: Config, speaker: Speaker,
                 actions: ModuleType = default_actions,
                 projector: ModuleType = default_projector,
                 files: FileIndex | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.config = config
        self.speaker = speaker
        self.actions = actions
        self.projector = projector
        self.files = files or FileIndex(config.file_folders or None)
        self.clock = clock
        self.lang = config.lang
        self.awake_until = 0.0
        self.last_kind: str | None = None  # type du dernier fichier affiché
        self.lock = threading.RLock()  # la télécommande agit depuis un autre fil

    # ------------------------------------------------------------ dialogue

    def tell(self, key: str, lang: str | None = None, **kwargs) -> None:
        lang = lang or self.lang
        self.speaker.say(say(lang, key, **kwargs), lang)

    def greet(self, text_mode: bool = False) -> None:
        self.tell("ready_text" if text_mode else "ready")

    def wake(self) -> None:
        self.awake_until = self.clock() + self.config.awake_seconds
        self.tell("yes")

    def is_awake(self) -> bool:
        return self.clock() < self.awake_until

    def on_utterance(self, texts: dict[str, str], require_wake: bool = True) -> bool:
        """Traite une phrase. `texts` associe chaque langue au texte reconnu.

        Renvoie False quand l'utilisateur demande à Viky de s'arrêter.
        """
        with self.lock:
            return self._on_utterance(texts, require_wake)

    def _on_utterance(self, texts: dict[str, str], require_wake: bool) -> bool:
        heard_wake = False
        stripped: dict[str, str] = {}
        for lang, text in texts.items():
            found, rest = strip_wake_word(normalize(text), self.config.wake_words)
            heard_wake = heard_wake or found
            stripped[lang] = rest

        if require_wake and not heard_wake and not self.is_awake():
            return True

        order = [self.lang] + [lang for lang in texts if lang != self.lang]
        intent = parse_any(stripped, order)
        if intent is None:
            if heard_wake and not any(stripped.values()):
                self.wake()
            elif heard_wake or len(stripped.get(self.lang, "").split()) >= 2:
                self.tell("not_understood")
            return True

        keep_running = self.execute(intent)
        self.awake_until = self.clock() + self.config.awake_seconds
        return keep_running

    # ------------------------------------------------------------ actions

    def execute(self, intent: Intent) -> bool:
        handler = getattr(self, f"_do_{intent.name}", None)
        if handler is None:
            return True
        try:
            return handler(intent.lang, **intent.args) is not False
        except self.projector.NotAvailable:
            self.tell("not_available", intent.lang)
        except Exception:
            traceback.print_exc()
            self.tell("failed", intent.lang)
        return True

    # --- conversation

    def _do_quit(self, lang):
        self.tell("bye", lang)
        return False

    def _do_lang_fr(self, lang):
        self.lang = "fr"
        self.tell("lang")

    def _do_lang_en(self, lang):
        self.lang = "en"
        self.tell("lang")

    def _do_thanks(self, lang):
        self.tell("thanks", lang)

    def _do_greet(self, lang):
        self.tell("greet", lang)

    def _do_whoami(self, lang):
        self.tell("whoami", lang)

    def _do_help(self, lang):
        self.tell("help", lang)

    def _do_time(self, lang):
        self.speaker.say(time_sentence(lang, datetime.now()), lang)

    def _do_date(self, lang):
        self.speaker.say(date_sentence(lang, datetime.now()), lang)

    def _do_joke(self, lang):
        self.tell("jokes", lang)

    # --- applications, sites, système

    def _do_open(self, lang, target):
        act = self.actions
        kind, value = act.resolve_target(target, self.config.apps, self.config.sites)
        label = act.clean_target(target)
        if kind == "app" and not act.open_target(target, self.config.apps, self.config.sites):
            # Pas d'application à ce nom : c'est peut-être un fichier.
            path = self.files.find(target)
            if path is None:
                self.tell("open_failed", lang, name=label)
                return
            self._show_file(lang, path, on_projector=False)
            return
        if kind != "app":
            act.open_target(target, self.config.apps, self.config.sites)
        self.tell("opening", lang, name=label)

    def _do_close(self, lang, target):
        label = self.actions.clean_target(target)
        ok = self.actions.close_app(target, self.config.apps)
        self.tell("closing" if ok else "close_failed", lang, name=label)

    def _do_search(self, lang, query):
        self.tell("searching", lang, query=query)
        self.actions.web_search(query)

    def _do_youtube(self, lang, query):
        self.tell("youtube", lang, query=query)
        self.actions.youtube_search(query)

    def _volume(self, lang, direction, key):
        self.tell(key if self.actions.volume(direction) else "failed", lang)

    def _do_vol_up(self, lang):
        self._volume(lang, "up", "vol_up")

    def _do_vol_down(self, lang):
        self._volume(lang, "down", "vol_down")

    def _do_mute(self, lang):
        self._volume(lang, "mute", "mute")

    def _do_lock(self, lang):
        self.tell("lock", lang)
        if not self.actions.lock_screen():
            self.tell("failed", lang)

    def _do_screenshot(self, lang):
        self.tell("screenshot" if self.actions.screenshot() else "failed", lang)

    def _do_photo(self, lang):
        self.tell("smile", lang)
        self.tell("photo" if self.actions.take_photo() else "failed", lang)

    def _do_note(self, lang, text):
        self.actions.add_note(text)
        self.tell("note", lang)

    # --- fichiers et projecteur

    def _show_file(self, lang, path: Path, on_projector: bool) -> None:
        if on_projector and self.projector.projector() is None:
            self.tell("no_projector", lang)
            on_projector = False
        self.tell("projecting" if on_projector else "opening", lang, name=path.stem)
        self.projector.open_file(path, on_projector)
        self.last_kind = kind_of(path)

    def _do_open_file(self, lang, target):
        path = self.files.find(target)
        if path is None:
            self.tell("file_not_found", lang, name=self.actions.clean_target(target))
            return
        self._show_file(lang, path, on_projector=False)

    def _do_project(self, lang, target):
        if normalize(target) in _CURRENT_WORDS:
            return self._do_project_current(lang)
        path = self.files.find(target)
        if path is None:
            self.tell("file_not_found", lang, name=self.actions.clean_target(target))
            return
        self._show_file(lang, path, on_projector=True)

    def _do_project_current(self, lang):
        if self.projector.projector() is None:
            self.tell("no_projector", lang)
        elif not self.projector.project_current_window():
            self.tell("failed", lang)

    def _do_close_current(self, lang):
        if self.projector.slideshow_running():
            self.projector.slideshow_end()
        self.projector.press("alt", "f4")

    def _do_next(self, lang):
        if self.projector.slideshow_running():
            self.projector.slide_next()
        else:
            self.projector.press("right" if self.last_kind in ("img", "ppt") else "pagedown")

    def _do_previous(self, lang):
        if self.projector.slideshow_running():
            self.projector.slide_previous()
        else:
            self.projector.press("left" if self.last_kind in ("img", "ppt") else "pageup")

    def _do_goto(self, lang, n):
        number = parse_number(n)
        if number is None:
            self.tell("not_understood", lang)
            return
        self.projector.slide_goto(number)

    def _do_show_start(self, lang):
        self.projector.start_slideshow(presenter_view=self.config.presenter_view)
        self.last_kind = "ppt"

    def _do_show_end(self, lang):
        self.projector.slideshow_end()

    def _do_black(self, lang):
        self.projector.slideshow_black(True)

    def _do_resume(self, lang):
        self.projector.slideshow_black(False)

    def _do_fullscreen(self, lang):
        self.projector.press("f11")

    def _display(self, lang, mode):
        self.tell("ok" if self.projector.set_display_mode(mode) else "not_available", lang)

    def _do_display_clone(self, lang):
        self._display(lang, "clone")

    def _do_display_extend(self, lang):
        self._display(lang, "extend")

    def _do_display_external(self, lang):
        self._display(lang, "external")

    def _do_display_internal(self, lang):
        self._display(lang, "internal")

    # --- Excel et PowerPoint

    def _cell(self, lang, cell):
        name = parse_cell(cell)
        if name is None:
            self.tell("bad_cell", lang)
        return name

    def _do_cell_set(self, lang, cell, value):
        name = self._cell(lang, cell)
        if name:
            parsed = parse_value(value)
            self.projector.excel_set(name, parsed)
            self.tell("cell_set", lang, cell=name, value=_spoken(parsed))

    def _do_cell_get(self, lang, cell):
        name = self._cell(lang, cell)
        if name:
            value = self.projector.excel_get(name)
            if value in (None, ""):
                self.tell("cell_empty", lang, cell=name)
            else:
                self.tell("cell_get", lang, cell=name, value=_spoken(value))

    def _do_cell_clear(self, lang, cell):
        name = self._cell(lang, cell)
        if name:
            self.projector.excel_set(name, "")
            self.tell("ok", lang)

    def _do_save(self, lang):
        self.projector.save_active()
        self.tell("saved", lang)

    def _do_sheet_next(self, lang):
        self.speaker.say(self.projector.excel_sheet(1), lang)

    def _do_sheet_previous(self, lang):
        self.speaker.say(self.projector.excel_sheet(-1), lang)

    def _do_slide_title(self, lang, text):
        self.projector.set_slide_title(text[:1].upper() + text[1:])
        self.tell("title_set", lang)


def _spoken(value) -> str:
    """Affiche 12.0 comme « 12 » et 12.5 comme « 12,5 » quand Viky le prononce."""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value).replace(".", ",")
    return str(value)
