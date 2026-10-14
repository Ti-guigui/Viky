"""Le cerveau de Viky : décide quoi faire de chaque phrase entendue."""

from __future__ import annotations

import time
from datetime import datetime
from types import ModuleType
from typing import Callable, Protocol

from . import actions as default_actions
from .config import Config
from .intents import Intent, parse_any
from .messages import date_sentence, say, time_sentence
from .text import normalize, strip_wake_word


class Speaker(Protocol):
    def say(self, text: str, lang: str) -> None: ...


class Assistant:
    def __init__(self, config: Config, speaker: Speaker,
                 actions: ModuleType = default_actions,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.config = config
        self.speaker = speaker
        self.actions = actions
        self.clock = clock
        self.lang = config.lang
        self.awake_until = 0.0

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
        lang, args, act = intent.lang, intent.args, self.actions
        name = intent.name

        if name == "quit":
            self.tell("bye", lang)
            return False
        if name in ("lang_fr", "lang_en"):
            self.lang = name[-2:]
            self.tell("lang")
            return True

        simple = {"thanks", "greet", "whoami", "help"}
        if name in simple:
            self.tell(name, lang)
        elif name == "time":
            self.speaker.say(time_sentence(lang, datetime.now()), lang)
        elif name == "date":
            self.speaker.say(date_sentence(lang, datetime.now()), lang)
        elif name == "joke":
            self.tell("jokes", lang)
        elif name == "open":
            target = args["target"]
            label = act.clean_target(target)
            ok = act.open_target(target, self.config.apps, self.config.sites)
            self.tell("opening" if ok else "open_failed", lang, name=label)
        elif name == "close":
            label = act.clean_target(args["target"])
            ok = act.close_app(args["target"], self.config.apps)
            self.tell("closing" if ok else "close_failed", lang, name=label)
        elif name == "search":
            self.tell("searching", lang, query=args["query"])
            act.web_search(args["query"])
        elif name == "youtube":
            self.tell("youtube", lang, query=args["query"])
            act.youtube_search(args["query"])
        elif name in ("vol_up", "vol_down", "mute"):
            direction = {"vol_up": "up", "vol_down": "down", "mute": "mute"}[name]
            self.tell(name if act.volume(direction) else "failed", lang)
        elif name == "lock":
            self.tell("lock", lang)
            if not act.lock_screen():
                self.tell("failed", lang)
        elif name == "screenshot":
            self.tell("screenshot" if act.screenshot() else "failed", lang)
        elif name == "photo":
            self.tell("smile", lang)
            self.tell("photo" if act.take_photo() else "failed", lang)
        elif name == "note":
            act.add_note(args["text"])
            self.tell("note", lang)
        return True
