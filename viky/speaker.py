"""Synthèse vocale hors ligne (voix intégrées de Windows, macOS ou espeak sous Linux)."""

from __future__ import annotations

import re

_VOICE_HINTS = {
    "fr": r"(^|[^a-z])(fr|french|francais|hortense|julie|paul|amelie|thomas)([^a-z]|$)",
    "en": r"(^|[^a-z])(en|english|zira|david|mark|samantha|alex)([^a-z]|$)",
}


class Speaker:
    def __init__(self, rate: int = 180, mute: bool = False) -> None:
        self.engine = None
        self.voices: dict[str, str] = {}
        if mute:
            return
        try:
            import pyttsx3

            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", rate)
            self.voices = self._find_voices()
        except Exception as error:  # pas de voix disponible : Viky écrit seulement
            print(f"[Viky] Synthèse vocale indisponible ({error}). Les réponses seront affichées.")
            self.engine = None

    def _find_voices(self) -> dict[str, str]:
        found: dict[str, str] = {}
        for voice in self.engine.getProperty("voices"):
            languages = [lang.decode(errors="ignore") if isinstance(lang, bytes) else str(lang)
                         for lang in (voice.languages or [])]
            description = " ".join([voice.id, voice.name or "", *languages]).lower()
            for lang, hint in _VOICE_HINTS.items():
                if lang not in found and re.search(hint, description):
                    found[lang] = voice.id
        for lang in _VOICE_HINTS:
            if lang not in found:
                print(f"[Viky] Aucune voix « {lang} » installée : la voix par défaut sera utilisée.")
        return found

    def say(self, text: str, lang: str) -> None:
        print(f"Viky : {text}")
        if self.engine is None:
            return
        if lang in self.voices:
            self.engine.setProperty("voice", self.voices[lang])
        self.engine.say(text)
        self.engine.runAndWait()
