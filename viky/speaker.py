"""Synthèse vocale hors ligne (voix intégrées de Windows, macOS ou espeak sous Linux).

La voix tourne dans son propre fil d'exécution : le micro et la télécommande
du téléphone peuvent donc faire parler Viky sans se marcher dessus.
"""

from __future__ import annotations

import queue
import re
import threading

_VOICE_HINTS = {
    "fr": r"(^|[^a-z])(fr|french|francais|hortense|julie|paul|amelie|thomas)([^a-z]|$)",
    "en": r"(^|[^a-z])(en|english|zira|david|mark|samantha|alex)([^a-z]|$)",
}


class Speaker:
    def __init__(self, rate: int = 180, mute: bool = False) -> None:
        self.rate = rate
        self.voices: dict[str, str] = {}
        self.enabled = not mute
        self._jobs: queue.Queue = queue.Queue()
        if self.enabled:
            ready = threading.Event()
            threading.Thread(target=self._run, args=(ready,), daemon=True, name="voix").start()
            ready.wait(timeout=10)

    def _run(self, ready: threading.Event) -> None:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            self.voices = self._find_voices(engine)
        except Exception as error:  # pas de voix disponible : Viky écrit seulement
            print(f"[Viky] Synthèse vocale indisponible ({error}). Les réponses seront affichées.")
            self.enabled = False
            ready.set()
            return
        ready.set()
        while True:
            text, lang, done = self._jobs.get()
            try:
                if lang in self.voices:
                    engine.setProperty("voice", self.voices[lang])
                engine.say(text)
                engine.runAndWait()
            except Exception as error:
                print(f"[Viky] Erreur de synthèse vocale : {error}")
            finally:
                done.set()

    @staticmethod
    def _find_voices(engine) -> dict[str, str]:
        found: dict[str, str] = {}
        for voice in engine.getProperty("voices"):
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
        """Prononce le texte et attend la fin de la phrase."""
        print(f"Viky : {text}")
        if not self.enabled:
            return
        done = threading.Event()
        self._jobs.put((text, lang, done))
        done.wait(timeout=120)
