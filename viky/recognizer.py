"""Reconnaissance vocale hors ligne avec Vosk."""

from __future__ import annotations

import json
from pathlib import Path

from .audio import SAMPLE_RATE


class ModelMissing(Exception):
    pass


class Recognizer:
    """Transcrit une phrase avec un modèle Vosk par langue."""

    def __init__(self, langs: list[str], models_dir: Path) -> None:
        from vosk import KaldiRecognizer, Model, SetLogLevel

        SetLogLevel(-1)
        self.recognizers = {}
        missing = []
        for lang in langs:
            path = models_dir / f"vosk-{lang}"
            if path.exists():
                self.recognizers[lang] = KaldiRecognizer(Model(str(path)), SAMPLE_RATE)
            else:
                missing.append(lang)
        if not self.recognizers:
            raise ModelMissing(", ".join(missing))
        for lang in missing:
            print(f"[Viky] Modèle « {lang} » absent : cette langue est ignorée.")

    def transcribe(self, audio: bytes) -> dict[str, str]:
        texts = {}
        for lang, recognizer in self.recognizers.items():
            recognizer.AcceptWaveform(audio)
            texts[lang] = json.loads(recognizer.FinalResult()).get("text", "")
        return texts
