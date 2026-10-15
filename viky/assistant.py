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
from . import system as default_system
from . import news as news_feeds
from . import projector as default_projector
from .brain import Brain, BrainUnavailable
from .config import Config
from .files import FileIndex, kind_of, split_kind
from .intents import Intent, parse_any
from .magic import STAGE_PERSONA, SUSPENSE, MagicShow, parse_card
from . import mail as mail_module
from .agenda import Agenda, day_range
from .memory import Memory
from .reminders import Reminder, Reminders, parse_duration, parse_reminder
from .messages import date_sentence, say, time_sentence
from .numbers import parse_cell, parse_number, parse_value
from .report import save_report
from .text import normalize, strip_wake_word, tidy
from .weather import Weather

_CURRENT_WORDS = {"ca", "cela", "ceci", "la fenetre", "le fichier", "it", "this", "the window"}


class Speaker(Protocol):
    def say(self, text: str, lang: str) -> None: ...


class Assistant:
    def __init__(self, config: Config, speaker: Speaker,
                 actions: ModuleType = default_actions,
                 projector: ModuleType = default_projector,
                 files: FileIndex | None = None,
                 brain: Brain | None = None,
                 weather: Weather | None = None,
                 news: ModuleType = news_feeds,
                 stage=None,
                 system: ModuleType = default_system,
                 memory: Memory | None = None,
                 reminders: Reminders | None = None,
                 agenda: Agenda | None = None,
                 mailer: ModuleType = mail_module,
                 clock: Callable[[], float] = time.monotonic,
                 pause: Callable[[float], None] = time.sleep) -> None:
        self.config = config
        self.speaker = speaker
        self.actions = actions
        self.projector = projector
        self.files = files or FileIndex(config.file_folders or None)
        self.brain = brain if brain is not None else Brain(
            config.claude_model, config.claude_key, config.local_model, config.ollama_url,
            config.use_claude, config.use_local)
        self.weather = weather or Weather(config.city)
        self.news = news
        self.headlines: list = []
        self.last_report: Path | None = None
        self.magic: MagicShow = config.magic
        self.pause = pause
        if stage is None:
            from .stage import Stage

            stage = Stage(self._projector_rect)
        self.stage = stage
        self.system = system
        data = config.data_dir
        self.memory = memory or Memory(data / "memoire.json")
        self.reminders = reminders or Reminders(data / "rappels.json")
        self.reminders.on_due = self._on_reminder
        self.brain.context = self.memory.context
        self.pending = None  # (action, échéance) : action en attente d'un « confirme »
        self.dialog = None  # (fonction, échéance) : Viky attend la réponse à une question
        self.mailer = mailer
        self.mail_accounts = config.mail_accounts()
        self.agenda = agenda or config.agenda()
        self.last_mails: list = []
        self.listeners: list = []  # interface graphique : reçoit les événements de Viky
        self._set_persona()
        self.clock = clock
        self.lang = config.lang
        self.awake_until = 0.0
        self.last_kind: str | None = None  # type du dernier fichier affiché
        self.lock = threading.RLock()  # la télécommande agit depuis un autre fil

    # ------------------------------------------------------------ dialogue

    def tell(self, key: str, lang: str | None = None, **kwargs) -> None:
        lang = lang or self.lang
        self.speak(say(lang, key, **kwargs), lang)

    def speak(self, text: str, lang: str | None = None) -> None:
        self.emit("reply", text)
        self.speaker.say(text, lang or self.lang)

    def emit(self, event: str, value=None) -> None:
        """Prévient l'interface graphique (écoute, réflexion, réponse…)."""
        for listener in self.listeners:
            try:
                listener(event, value)
            except Exception:
                traceback.print_exc()

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
        if self.magic.stage_mode and self._stage_cue(texts):
            return True
        heard_wake = False
        stripped: dict[str, str] = {}
        for lang, text in texts.items():
            found, rest = strip_wake_word(tidy(text), self.config.wake_words)
            heard_wake = heard_wake or found
            stripped[lang] = rest

        if require_wake and not heard_wake and not self.is_awake():
            return True
        self.emit("heard", next((t for t in (texts.get(self.lang), *texts.values()) if t), ""))
        if self.dialog and self.clock() < self.dialog[1]:
            handler, _ = self.dialog
            self.dialog = None
            answer = next((t for t in (stripped.get(self.lang), *stripped.values()) if t), "")
            if normalize(answer) in ("annule", "laisse tomber", "non", "cancel", "never mind"):
                self.tell("cancelled")
            elif answer:
                try:
                    handler(self.lang, answer)
                except Exception:
                    traceback.print_exc()
                    self.tell("failed")
            self.awake_until = self.clock() + self.config.awake_seconds
            return True
        self.dialog = None

        order = [self.lang] + [lang for lang in texts if lang != self.lang]
        intent = parse_any(stripped, order)
        if intent is None:
            question = stripped.get(self.lang, "")
            if heard_wake and not any(stripped.values()):
                self.wake()
            elif len(question.split()) >= 3 and self.brain.available:
                # Phrase inconnue mais assez longue : on la pose à l'IA.
                intent = Intent("ask", self.lang, {"question": question})
            elif (heard_wake or len(question.split()) >= 2) and not self.magic.stage_mode:
                self.tell("not_understood")  # sur scène, Viky se tait plutôt que d'avouer
            if intent is None:
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
        except (self.system.NotSupported, ImportError):
            self.tell("not_available", intent.lang)
        except BrainUnavailable:
            self.tell("no_brain", intent.lang)
        except (FileNotFoundError, PermissionError):
            traceback.print_exc()
            self.tell("failed", intent.lang)
        except OSError:
            traceback.print_exc()
            self.tell("offline", intent.lang)
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
            self.tell("file_not_found", lang, name=split_kind(target)[1] or target)
            return
        self._show_file(lang, path, on_projector=False)

    def _do_project(self, lang, target):
        if normalize(target) in _CURRENT_WORDS:
            return self._do_project_current(lang)
        path = self.files.find(target)
        if path is None:
            self.tell("file_not_found", lang, name=split_kind(target)[1] or target)
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
        if self.projector.slideshow_running():
            self.projector.slideshow_black(True)
        else:
            self.stage.black()

    def _do_resume(self, lang):
        if self.projector.slideshow_running():
            self.projector.slideshow_black(False)
        self.stage.hide()

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

    def _do_slide_replace(self, lang, old, new):
        count = self.projector.replace_in_slide(old, new)
        if count:
            self.tell("replaced", lang, old=old, new=new)
        else:
            self.tell("text_not_found", lang, old=old)

    def _do_slide_title(self, lang, text):
        self.projector.set_slide_title(text[:1].upper() + text[1:])
        self.tell("title_set", lang)


    # --- météo et actualité

    def _do_weather(self, lang, text):
        sentence = self.weather.report(text, lang)
        if sentence is None:
            self.tell("place_not_found", lang)
        else:
            self.speaker.say(sentence, lang)

    def _do_news(self, lang):
        feeds = self.config.news_feeds.get(lang) or news_feeds.DEFAULT_FEEDS[lang]
        self.headlines = self.news.fetch_headlines(feeds, self.config.news_count)
        if not self.headlines:
            self.tell("offline", lang)
            return
        self.tell("news_intro", lang)
        for number, headline in enumerate(self.headlines, start=1):
            self.speaker.say(f"{number}. {headline.title}", lang)
        self.tell("news_outro", lang)

    def _do_news_detail(self, lang, n):
        if not self.headlines:
            self._do_news(lang)
            return
        if normalize(n) in ("dernier", "derniere", "last"):
            index = len(self.headlines)
        else:
            index = parse_number(n) or 0
        if not 1 <= index <= len(self.headlines):
            self.tell("news_bad_number", lang, count=len(self.headlines))
            return
        headline = self.headlines[index - 1]
        self.speaker.say(headline.title, lang)
        if not self.brain.available:
            self.speaker.say(headline.summary or say(lang, "no_brain"), lang)
            return
        self.tell("thinking", lang)
        article = self.news.fetch_article(headline)
        self.speaker.say(self.brain.explain_article(headline.title, article, lang), lang)

    # --- intelligence

    def _do_ask(self, lang, question):
        if not self.brain.available:
            self.tell("no_brain", lang)
            return
        self.tell("thinking", lang)
        self.speaker.say(self.brain.ask(question, lang), lang)

    def _do_followup(self, lang):
        if not self.brain.history:
            self.tell("not_understood", lang)
            return
        self.tell("thinking", lang)
        self.speaker.say(self.brain.follow_up(lang), lang)

    def _do_research(self, lang, query):
        if not self.brain.use_claude:
            self.tell("no_claude", lang)
            return
        self.tell("research_start", lang, query=query)
        spoken, report = self.brain.research(query, lang)
        self.last_report = save_report(query, report)
        self.speaker.say(spoken, lang)
        self.tell("research_saved", lang)

    def _do_show_report(self, lang, projector=None):
        if self.last_report is None:
            self.tell("no_report", lang)
            return
        self._show_file(lang, self.last_report, on_projector=bool(projector))


    # --- magie

    def _projector_rect(self):
        screen = self.projector.projector()
        return screen["rect"] if screen else None

    def _set_persona(self) -> None:
        self.brain.persona = STAGE_PERSONA if self.magic.stage_mode else None

    def _stage_cue(self, texts: dict[str, str]) -> bool:
        """Mots-codes et répliques préparées : déclenchés sans dire « Viky »."""
        for lang in [self.lang] + [l for l in texts if l != self.lang]:
            text = texts.get(lang, "")
            code = self.magic.find_code(text)
            if code:
                print(f"[magie] mot-code « {code.phrase} » -> {code.effect}")
                self.run_effect(code.effect, code.value, self.lang)
                return True
            reply = self.magic.find_reply(text)
            if reply:
                self.speaker.say(reply, self.lang)
                return True
        return False

    def run_effect(self, effect: str, value: str, lang: str) -> str:
        """Exécute un effet magique. Renvoie un petit message pour la télécommande."""
        if effect == "reveler":
            return self._reveal(lang)
        if effect == "deviner":
            return self._guess(lang)
        if effect == "noir":
            self._do_black(lang)
        elif effect == "effacer":
            self._do_resume(lang)
        elif effect == "dire" and value:
            self.speaker.say(value, lang)
        elif effect == "afficher" and value:
            self.stage.show_text(value, "machine")
        elif effect == "charger":
            self.magic.secret = value.strip()
            card = self.magic.card
            return f"chargé : {card.spoken(lang) if card else self.magic.secret}"
        elif effect == "projeter" and value:
            self._do_project(lang, value)
        elif effect == "suivant":
            self._do_next(lang)
        elif effect == "precedent":
            self._do_previous(lang)
        elif effect == "mode":
            self._set_stage_mode(not self.magic.stage_mode, lang, announce=False)
        else:
            return f"effet inconnu : {effect}"
        return "ok"

    def _reveal(self, lang) -> str:
        card = self.magic.card
        if card:
            self.stage.show_card(card, lang)
        elif self.magic.secret:
            self.stage.show_text(self.magic.secret)
        else:
            return "aucun secret chargé"
        return "révélé"

    def _guess(self, lang) -> str:
        if not self.magic.secret:
            self.tell("guess_blurry", lang)
            return "aucun secret chargé"
        for line in SUSPENSE[lang]:
            self.speaker.say(line, lang)
            self.pause(1.2)
        self.tell("guess_reveal", lang, secret=self.magic.secret_spoken(lang))
        self._reveal(lang)
        return "deviné"

    def _set_stage_mode(self, on: bool, lang, announce: bool = True) -> None:
        self.magic.stage_mode = on
        self._set_persona()
        self.emit("stage", on)
        if announce:
            self.tell("stage_on" if on else "stage_off", lang)

    def _do_stage_on(self, lang):
        self._set_stage_mode(True, lang)

    def _do_stage_off(self, lang):
        self._set_stage_mode(False, lang)

    def _do_reveal(self, lang):
        if self._reveal(lang) == "aucun secret chargé":
            self.tell("guess_blurry", lang)

    def _do_guess(self, lang):
        self._guess(lang)

    def _do_show_text(self, lang, text):
        self.stage.show_text(text[:1].upper() + text[1:], "machine")

    def _do_clear_stage(self, lang):
        self.stage.hide()

    def remote_action(self, action: str, value: str) -> dict:
        """Appelé par la télécommande du téléphone (depuis un autre fil)."""
        message = ""
        if action != "etat":
            with self.lock:
                try:
                    if action == "secret":
                        action = "charger"
                    message = self.run_effect(action, value, self.lang)
                except Exception as error:
                    traceback.print_exc()
                    message = f"erreur : {error}"
        card = self.magic.card
        return {"secret": card.spoken(self.lang) if card else self.magic.secret,
                "spectacle": self.magic.stage_mode, "message": message}


    # --- interface

    def _do_ui_hud(self, lang):
        self.emit("show_hud")

    def _do_ui_widget(self, lang):
        self.emit("show_widget")

    def hud_data(self, slow: bool) -> dict:
        """Informations affichées par le HUD (appelé régulièrement depuis un autre fil)."""
        if slow and self.agenda.configured:
            try:
                start, end, _ = day_range("aujourd'hui", datetime.now())
                self._hud_events = [f"{e.start:%H:%M} — {e.title}" if not e.all_day else f"Journée — {e.title}"
                                    for e in self.agenda.events(start, end)]
            except Exception:
                pass
        info: dict = {"reminders": getattr(self, "_hud_events", []) +
                      [f"{_when_words(r.when, self.lang)} — {r.text}" for r in self.reminders.upcoming()[:5]]}
        try:
            info["status"] = self.system.status()
        except Exception:
            pass
        if slow:
            try:
                info["weather"] = self.weather.report("", self.lang)
            except Exception:
                pass
            try:
                feeds = self.config.news_feeds.get(self.lang) or news_feeds.DEFAULT_FEEDS[self.lang]
                info["news"] = [h.title for h in self.news.fetch_headlines(feeds, 5)]
            except Exception:
                pass
        return info

    # --- mémoire

    def _do_greet(self, lang):
        if self.memory.name:
            self.speak(("Bonjour " if lang == "fr" else "Hello ") + self.memory.name + " !", lang)
        else:
            self.tell("greet", lang)

    def _do_set_name(self, lang, name):
        self.memory.set_name(name)
        self.tell("name_set", lang, name=self.memory.name)

    def _do_remember(self, lang, fact):
        self.memory.remember(fact)
        self.tell("remembered", lang)

    def _do_recall(self, lang):
        if not self.memory.name and not self.memory.facts:
            self.tell("memory_empty", lang)
            return
        if self.memory.name:
            self.tell("recall_name", lang, name=self.memory.name)
        for fact in self.memory.facts[-5:]:
            self.speak(fact["texte"], lang)

    def _do_forget(self, lang):
        self.memory.forget_all()
        self.tell("forgotten", lang)

    # --- rappels et minuteurs

    def _do_timer(self, lang, duration):
        seconds = parse_duration(duration)
        if not seconds:
            self.tell("bad_duration", lang)
            return
        label = _duration_words(seconds, lang)
        self.reminders.add(time.time() + seconds, label, "minuteur")
        self.tell("timer_set", lang, duration=label)

    def _do_remind(self, lang, rest=""):
        due, what = parse_reminder(rest, datetime.now())
        if due is None:
            self.tell("remind_when", lang)
            return
        what = what or ("rappel" if lang == "fr" else "reminder")
        self.reminders.add(due.timestamp(), what)
        self.tell("reminder_set", lang, when=_when_words(due, lang), what=what)

    def _do_list_reminders(self, lang):
        upcoming = self.reminders.upcoming()
        if not upcoming:
            self.tell("no_reminders", lang)
            return
        self.tell("reminders_intro", lang, count=len(upcoming))
        for reminder in upcoming[:5]:
            self.speak(f"{_when_words(reminder.when, lang)} : {reminder.text}", lang)

    def _do_clear_reminders(self, lang):
        self.reminders.clear()
        self.tell("reminders_cleared", lang)

    def _on_reminder(self, reminder: Reminder) -> None:
        """Appelé par le fil des rappels quand un rappel arrive à échéance."""
        with self.lock:
            self.emit("reminder", reminder.text)
            try:
                self.system.beep()
            except Exception:
                pass
            if reminder.kind == "minuteur":
                self.tell("timer_done", duration=reminder.text)
            else:
                self.tell("reminder_due", what=reminder.text)

    def _do_briefing(self, lang):
        now = datetime.now()
        hello = say(lang, "briefing_hello_morning" if now.hour < 18 else "briefing_hello_evening")
        if self.memory.name:
            hello = hello.rstrip(".!") + f", {self.memory.name}."
        self.speak(hello, lang)
        self.speak(date_sentence(lang, now) + " " + time_sentence(lang, now), lang)
        try:
            weather = self.weather.report("", lang)
            if weather:
                self.speak(weather, lang)
        except OSError:
            pass
        if self.agenda.configured:
            try:
                start, end, _ = day_range("aujourd'hui", now)
                self._say_events(lang, self.agenda.events(start, end), "aujourd'hui")
            except Exception:
                traceback.print_exc()
        today = self.reminders.today(now)
        if today:
            self.tell("reminders_intro", lang, count=len(today))
            for reminder in today[:5]:
                self.speak(f"{_when_words(reminder.when, lang)} : {reminder.text}", lang)
        try:
            feeds = self.config.news_feeds.get(lang) or news_feeds.DEFAULT_FEEDS[lang]
            self.headlines = self.news.fetch_headlines(feeds, self.config.news_count)
        except OSError:
            self.headlines = []
        if self.headlines:
            self.tell("briefing_news", lang)
            for number, headline in enumerate(self.headlines[:3], start=1):
                self.speak(f"{number}. {headline.title}", lang)
        self.tell("briefing_end", lang)

    # --- e-mails

    def _accounts(self, lang) -> list:
        if not self.mail_accounts:
            self.tell("mail_not_configured", lang)
        return self.mail_accounts

    def _do_mail_check(self, lang):
        accounts = self._accounts(lang)
        if not accounts:
            return
        total, mails = 0, []
        for account in accounts:
            count, recent = self.mailer.unread(account, limit=5)
            total += count
            mails += recent
        mails.sort(key=lambda m: m.date.timestamp() if m.date else 0, reverse=True)
        self.last_mails = mails[:5]
        if not total:
            self.tell("mail_none", lang)
            return
        self.tell("mail_count", lang, count=total)
        for number, item in enumerate(self.last_mails, start=1):
            self.tell("mail_line", lang, n=number, sender=item.sender, subject=item.subject)
        self.tell("mail_hint", lang)

    def _do_mail_read(self, lang, n):
        if not self.last_mails:
            self._do_mail_check(lang)
            return
        index = parse_number(n) or 0
        if not 1 <= index <= len(self.last_mails):
            self.tell("news_bad_number", lang, count=len(self.last_mails))
            return
        item = self.last_mails[index - 1]
        text = self.mailer.body(item)
        self.tell("mail_header", lang, sender=item.sender, subject=item.subject)
        if len(text) > 500 and self.brain.available:
            self.tell("thinking", lang)
            prompt = ("Résume cet e-mail à l'oral en 3 ou 4 phrases :\n\n" if lang == "fr"
                      else "Summarize this e-mail out loud in 3 or 4 sentences:\n\n")
            self.speak(self.brain.ask(prompt + text, lang), lang)
        else:
            self.speak(text[:600] or say(lang, "mail_empty"), lang)

    def _contact(self, lang, name: str) -> tuple[str, str] | None:
        """Adresse d'un contact (section [contacts] de config.toml) ou adresse dictée."""
        key = normalize(name)
        for contact, address in self.config.contacts.items():
            if key == contact or key in contact.split() or contact in key:
                return contact.title(), address
        address = self.mailer.spoken_address(name)
        if address:
            return address, address
        self.tell("contact_unknown", lang, name=name)
        return None

    def _send_mail(self, lang, name, address, text, attachments=None, subject=None):
        account = next((a for a in self.mail_accounts if a.provider == self.config.mail_sender),
                       self.mail_accounts[0])
        text = text[:1].upper() + text[1:]
        subject = subject or (" ".join(text.split()[:7]) + ("…" if len(text.split()) > 7 else ""))
        signature = f"\n\n{self.memory.name}" if self.memory.name else ""
        message = self.mailer.build_message(account, address, subject, text + signature,
                                            self.memory.name or "", attachments)

        def send():
            self.mailer.send(account, message)
            self.tell("mail_sent", lang, name=name)

        what = f"{attachments[0].name}" if attachments else text
        self.confirm(lang, "mail_confirm", send, name=name, account=account.label, text=what)

    def _do_mail_send(self, lang, to, body=None):
        if not self._accounts(lang):
            return
        contact = self._contact(lang, to)
        if contact is None:
            return
        name, address = contact
        if body:
            self._send_mail(lang, name, address, body)
        else:
            self.ask(lang, "mail_what", lambda lang, text: self._send_mail(lang, name, address, text), name=name)

    def _do_mail_file(self, lang, file, to):
        if not self._accounts(lang):
            return
        path = self.files.find(file)
        if path is None:
            self.tell("file_not_found", lang, name=split_kind(file)[1] or file)
            return
        contact = self._contact(lang, to)
        if contact is None:
            return
        name, address = contact
        text = say(lang, "mail_file_body", name=path.stem)
        self._send_mail(lang, name, address, text, [path], subject=path.stem)

    # --- agenda

    def _say_events(self, lang, events, label) -> None:
        if not events:
            self.tell("agenda_empty", lang, label=label)
            return
        self.tell("agenda_count", lang, label=label[:1].upper() + label[1:], count=len(events))
        several_days = len({e.start.date() for e in events}) > 1
        for event in events[:8]:
            day = (f"{WEEKDAYS[lang][event.start.weekday()]} " if several_days else "")
            if event.all_day:
                self.speak(f"{day}{say(lang, 'all_day')} : {event.title}", lang)
            else:
                clock = f"{event.start.hour} h {event.start.minute:02d}" if event.start.minute else f"{event.start.hour} h"
                self.speak(f"{day}{'à' if lang == 'fr' else 'at'} {clock} : {event.title}", lang)

    def _do_agenda(self, lang, text):
        if not self.agenda.configured:
            self.tell("agenda_not_configured", lang)
            return
        start, end, label = day_range(text, datetime.now())
        events = self.agenda.events(start, end)
        if label == "prochain":
            events = events[:1]
            label = "prochainement" if lang == "fr" else "next"
        self._say_events(lang, events, label)

    def _do_agenda_add(self, lang, rest=""):
        if not self.agenda.can_add:
            self.tell("agenda_not_configured", lang)
            return
        due, what = parse_reminder(rest, datetime.now())
        if due is None:
            self.tell("remind_when", lang)
            return
        what = what or ("Rendez-vous" if lang == "fr" else "Appointment")
        what = what[:1].upper() + what[1:]
        calendar = self.agenda.add(what, due)
        self.tell("agenda_added", lang, what=what, when=_when_words(due, lang), calendar=calendar)

    # --- contrôle du PC

    def _do_status(self, lang):
        info = self.system.status()
        parts = []
        if "battery" in info:
            key = "status_battery_plugged" if info["plugged"] else "status_battery"
            parts.append(say(lang, key, battery=info["battery"]))
        parts.append(say(lang, "status_load", cpu=info["cpu"], ram=info["ram"]))
        self.speak(" ".join(parts), lang)

    def _do_wifi(self, lang):
        name = self.system.wifi_name()
        self.tell("wifi_on" if name else "wifi_off", lang, name=name)

    def _brightness(self, lang, change=None, level=None):
        value = self.system.brightness(change=change, level=level)
        self.tell("brightness", lang, level=value)

    def _do_brightness_up(self, lang):
        self._brightness(lang, change=20)

    def _do_brightness_down(self, lang):
        self._brightness(lang, change=-20)

    def _do_brightness_set(self, lang, level):
        word = normalize(level)
        value = 100 if "max" in word else 10 if "min" in word else parse_number(word.replace("pour cent", ""))
        if value is None:
            self.tell("not_understood", lang)
            return
        self._brightness(lang, level=value)

    def _do_media_pause(self, lang):
        self.system.media("play_pause")

    def _do_media_next(self, lang):
        self.system.media("next")

    def _do_media_previous(self, lang):
        self.system.media("previous")

    def _do_desktop(self, lang):
        self.system.show_desktop()

    def _do_switch_window(self, lang):
        self.system.switch_window()

    def _do_maximize(self, lang):
        self.system.maximize_window()

    def _do_minimize(self, lang):
        self.system.minimize_window()

    def ask(self, lang, key: str, handler, **kwargs) -> None:
        """Pose une question ; la prochaine phrase (sans « Viky ») sera la réponse."""
        self.dialog = (handler, self.clock() + 30)
        self.awake_until = self.clock() + 30
        self.tell(key, lang, **kwargs)

    def confirm(self, lang, key: str, action, **kwargs) -> None:
        """Demande « confirme » avant une action importante (arrêt du PC, envoi d'un e-mail…)."""
        self.pending = (action, self.clock() + 30)
        self.awake_until = self.clock() + 30
        self.tell(key, lang, **kwargs)

    def _ask_power(self, lang, action):
        def run():
            self.tell(f"doing_{action}", lang)
            self.system.power(action)
            self.last_power = action
        self.confirm(lang, f"confirm_{action}", run)

    def _do_shutdown(self, lang):
        self._ask_power(lang, "shutdown")

    def _do_restart(self, lang):
        self._ask_power(lang, "restart")

    def _do_sleep(self, lang):
        self._ask_power(lang, "sleep")

    def _do_confirm(self, lang):
        if not self.pending or self.clock() > self.pending[1]:
            self.pending = None
            self.tell("ok", lang)
            return
        action = self.pending[0]
        self.pending = None
        action()

    def _do_cancel(self, lang):
        if self.pending:
            self.pending = None
            self.tell("cancelled", lang)
        elif getattr(self, "last_power", None) in ("shutdown", "restart"):
            self.system.power("cancel")
            self.last_power = None
            self.tell("power_cancelled", lang)
        else:
            self.tell("ok", lang)


WEEKDAYS = {"fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
            "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}


def _duration_words(seconds: int, lang: str) -> str:
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    names = {"fr": ("heure", "minute", "seconde"), "en": ("hour", "minute", "second")}[lang]
    parts = [f"{n} {name}{'s' if n > 1 else ''}" for n, name in zip((hours, minutes, secs), names) if n]
    return (" et " if lang == "fr" else " and ").join(parts)


def _when_words(moment: datetime, lang: str) -> str:
    now = datetime.now()
    clock = (f"{moment.hour} h {moment.minute:02d}" if moment.minute else f"{moment.hour} h") if lang == "fr" \
        else moment.strftime("%I:%M %p").lstrip("0")
    if moment.date() == now.date():
        return ("aujourd'hui à " if lang == "fr" else "today at ") + clock
    if (moment.date() - now.date()).days == 1:
        return ("demain à " if lang == "fr" else "tomorrow at ") + clock
    return (f"le {moment.day}/{moment.month} à " if lang == "fr" else f"on {moment.month}/{moment.day} at ") + clock


def _spoken(value) -> str:
    """Affiche 12.0 comme « 12 » et 12.5 comme « 12,5 » quand Viky le prononce."""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value).replace(".", ",")
    return str(value)
