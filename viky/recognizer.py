"""Reconnaissance vocale hors ligne.

- Whisper (faster-whisper) : très précis, utilise la carte graphique NVIDIA si elle est
  disponible, sinon le processeur. Recommandé.
- Vosk : léger et rapide, moins précis. Utilisé en secours.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .audio import SAMPLE_RATE


class ModelMissing(Exception):
    pass


class VoskRecognizer:
    """Transcrit une phrase avec un modèle Vosk par langue."""

    name = "Vosk"

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


# Compatibilité avec l'ancien nom
Recognizer = VoskRecognizer


def _enable_cuda_dlls() -> None:
    """Sous Windows, rend visibles les bibliothèques CUDA installées par pip (nvidia-cublas, nvidia-cudnn)."""
    if sys.platform != "win32":
        return
    for package in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_runtime"):
        try:
            module = __import__(package, fromlist=["__path__"])
        except ImportError:
            continue
        for root in module.__path__:
            folder = Path(root) / "bin"
            if folder.exists():
                os.add_dll_directory(str(folder))
                os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")


def has_cuda() -> bool:
    """Vrai si une carte graphique NVIDIA utilisable est présente."""
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def pick_size(size: str, device: str) -> str:
    """« auto » : large-v3-turbo sur carte graphique (très précis et rapide), small sur processeur."""
    if size != "auto":
        return size
    return "large-v3-turbo" if device == "cuda" else "small"


class WhisperRecognizer:
    """Transcrit avec Whisper ; détecte seul la langue parlée."""

    name = "Whisper"

    def __init__(self, langs: list[str], models_dir: Path, size: str = "auto", device: str = "auto",
                 wake_words: list[str] | None = None) -> None:
        from faster_whisper import WhisperModel

        self.langs = langs
        # Le prénom dans la consigne aide Whisper à écrire « Viky » et pas « Vicky » ou « Mickey ».
        self.prompt = "Viky. " if not wake_words else f"{wake_words[0].capitalize()}. "
        download = models_dir / "whisper"
        attempts = [("cuda", "float16"), ("cpu", "int8")] if device in ("auto", "cuda") else [("cpu", "int8")]
        error = None
        for dev, compute in attempts:
            try:
                if dev == "cuda":
                    _enable_cuda_dlls()
                self.size = pick_size(size, dev)
                self.model = WhisperModel(self.size, device=dev, compute_type=compute, download_root=str(download))
                if dev == "cuda":
                    self._check()  # échoue tout de suite si les bibliothèques CUDA manquent
                self.device = dev
                return
            except Exception as exc:  # pas de carte NVIDIA ou CUDA incomplet : on passe au processeur
                error = exc
        raise RuntimeError(f"Whisper indisponible : {error}")

    def _check(self) -> None:
        import numpy as np

        list(self.model.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32), language=self.langs[0])[0])

    def transcribe(self, audio: bytes) -> dict[str, str]:
        import numpy as np

        samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        segments, info = self.model.transcribe(samples, beam_size=1, initial_prompt=self.prompt,
                                               condition_on_previous_text=False, vad_filter=False)
        lang = info.language
        if lang not in self.langs:  # langue inattendue : on impose la langue principale
            lang = self.langs[0]
            segments, _ = self.model.transcribe(samples, beam_size=1, language=lang, initial_prompt=self.prompt,
                                                condition_on_previous_text=False)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if text.strip(" .") == self.prompt.strip(" ."):  # Whisper répète parfois la consigne sur un silence
            text = ""
        return {lang: text}


def make_recognizer(engine: str, langs: list[str], models_dir: Path, size: str = "auto",
                    device: str = "auto", wake_words: list[str] | None = None):
    """Choisit le meilleur moteur disponible : Whisper, sinon Vosk."""
    if engine == "whisper":
        try:
            recognizer = WhisperRecognizer(langs, models_dir, size, device, wake_words)
            where = "carte graphique" if recognizer.device == "cuda" else "processeur"
            print(f"[Viky] Reconnaissance vocale Whisper ({recognizer.size}) sur le {where}.")
            return recognizer
        except Exception as error:
            print(f"[Viky] {error}. Utilisation de Vosk.")
    return VoskRecognizer(langs, models_dir)
