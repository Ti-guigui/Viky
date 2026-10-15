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
from . import news as news_feeds
from . import projector as default_projector
from .brain import Brain, BrainUnavailable
from .config import Config
from .files import FileIndex, kind_of, split_kind
from .intents import Intent, parse_any
from .magic import STAGE_PERSONA, SUSPENSE, MagicShow, parse_card
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
        self._set_persona()
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
        except BrainUnavailable:
            self.tell("no_brain", intent.lang)
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


def _spoken(value) -> str:
    """Affiche 12.0 comme « 12 » et 12.5 comme « 12,5 » quand Viky le prononce."""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value).replace(".", ",")
    return str(value)
