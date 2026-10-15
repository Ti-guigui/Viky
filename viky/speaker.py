"""Voix de Viky.

Deux moteurs, tous deux hors ligne :
- Piper : voix naturelle de qualité (recommandé) ;
- les voix intégrées du système (Windows, macOS, espeak) en secours.

La voix tourne dans son propre fil d'exécution : le micro et la télécommande
du téléphone peuvent donc faire parler Viky sans se marcher dessus.
"""

from __future__ import annotations

import queue
import re
import threading
from pathlib import Path
from typing import Callable

_VOICE_HINTS = {
    "fr": r"(^|[^a-z])(fr|french|francais|hortense|julie|paul|amelie|thomas)([^a-z]|$)",
    "en": r"(^|[^a-z])(en|english|zira|david|mark|samantha|alex)([^a-z]|$)",
}


class PiperEngine:
    """Voix naturelles Piper (fichiers .onnx dans models/piper)."""

    def __init__(self, voices: dict[str, Path], speed: float = 1.0) -> None:
        from piper import PiperVoice

        self.models = {lang: PiperVoice.load(str(path)) for lang, path in voices.items() if path.exists()}
        if not self.models:
            raise FileNotFoundError("aucune voix Piper installée")
        self.speed = speed

    def speak(self, text: str, lang: str) -> None:
        import numpy as np
        import sounddevice as sd
        from piper.config import SynthesisConfig

        voice = self.models.get(lang) or next(iter(self.models.values()))
        settings = SynthesisConfig(length_scale=1 / max(0.5, self.speed))
        chunks = list(voice.synthesize(text, syn_config=settings))
        if not chunks:
            return
        audio = np.concatenate([chunk.audio_float_array for chunk in chunks]).astype(np.float32)
        sd.play(audio, chunks[0].sample_rate)
        sd.wait()


class SystemEngine:
    """Voix intégrées du système, via pyttsx3."""

    def __init__(self, rate: int) -> None:
        import pyttsx3

        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)
        self.voices = self._find_voices()

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
                print(f"[Viky] Aucune voix système « {lang} » installée : la voix par défaut sera utilisée.")
        return found

    def speak(self, text: str, lang: str) -> None:
        if lang in self.voices:
            self.engine.setProperty("voice", self.voices[lang])
        self.engine.say(text)
        self.engine.runAndWait()


class Speaker:
    def __init__(self, rate: int = 180, mute: bool = False, engine: str = "piper",
                 piper_voices: dict[str, Path] | None = None, piper_speed: float = 1.0) -> None:
        self.rate = rate
        self.enabled = not mute
        self.engine_name = engine
        self.piper_voices = piper_voices or {}
        self.piper_speed = piper_speed
        self.on_state: Callable[[str], None] | None = None  # « speaking » / « idle » pour l'interface
        self._jobs: queue.Queue = queue.Queue()
        if self.enabled:
            ready = threading.Event()
            threading.Thread(target=self._run, args=(ready,), daemon=True, name="voix").start()
            ready.wait(timeout=30)

    def _make_engine(self):
        if self.engine_name == "piper":
            try:
                engine = PiperEngine(self.piper_voices, self.piper_speed)
                print("[Viky] Voix naturelle Piper activée.")
                return engine
            except Exception as error:
                print(f"[Viky] Voix Piper indisponible ({error}) : voix du système utilisée. "
                      "Lancez « python -m viky --telecharger-modeles » pour l'installer.")
        return SystemEngine(self.rate)

    def _run(self, ready: threading.Event) -> None:
        try:
            engine = self._make_engine()
        except Exception as error:  # aucune voix disponible : Viky écrit seulement
            print(f"[Viky] Synthèse vocale indisponible ({error}). Les réponses seront affichées.")
            self.enabled = False
            ready.set()
            return
        ready.set()
        while True:
            text, lang, done = self._jobs.get()
            try:
                self._state("speaking")
                engine.speak(text, lang)
            except Exception as error:
                print(f"[Viky] Erreur de synthèse vocale : {error}")
            finally:
                self._state("idle")
                done.set()

    def _state(self, state: str) -> None:
        if self.on_state:
            try:
                self.on_state(state)
            except Exception:
                pass

    def say(self, text: str, lang: str) -> None:
        """Prononce le texte et attend la fin de la phrase."""
        print(f"Viky : {text}")
        if not self.enabled:
            return
        done = threading.Event()
        self._jobs.put((text, lang, done))
        done.wait(timeout=120)
