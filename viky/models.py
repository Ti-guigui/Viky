"""Téléchargement des modèles de reconnaissance vocale Vosk (une seule fois)."""

from __future__ import annotations

import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

MODEL_URLS = {
    "fr": "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip",
    "en": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
}


_last_percent = -1


def _progress(blocks: int, block_size: int, total: int) -> None:
    global _last_percent
    if total > 0:
        percent = min(100, blocks * block_size * 100 // total)
        if percent != _last_percent:
            _last_percent = percent
            print(f"\r  {percent:3d} %", end="", flush=True)


def download_model(lang: str, models_dir: Path) -> Path:
    target = models_dir / f"vosk-{lang}"
    if target.exists():
        print(f"Modèle « {lang} » déjà présent.")
        return target
    models_dir.mkdir(parents=True, exist_ok=True)
    print(f"Téléchargement du modèle « {lang} » (environ 40 à 50 Mo)…")
    with tempfile.TemporaryDirectory(dir=models_dir) as tmp:
        archive = Path(tmp) / "model.zip"
        urllib.request.urlretrieve(MODEL_URLS[lang], archive, _progress)
        print()
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp)
        extracted = next(p for p in Path(tmp).iterdir() if p.is_dir())
        shutil.move(str(extracted), target)
    print(f"Modèle « {lang} » installé.")
    return target


def piper_path(name: str, models_dir: Path) -> Path:
    return models_dir / "piper" / f"{name}.onnx"


def download_piper_voice(name: str, models_dir: Path) -> Path:
    """Télécharge une voix Piper, par exemple « fr_FR-siwis-medium » (environ 60 Mo)."""
    target = piper_path(name, models_dir)
    if target.exists():
        print(f"Voix « {name} » déjà présente.")
        return target
    locale, speaker, quality = name.split("-")
    base = (f"https://huggingface.co/rhasspy/piper-voices/resolve/main/"
            f"{locale.split('_')[0]}/{locale}/{speaker}/{quality}/{name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Téléchargement de la voix « {name} »…")
    for suffix in (".onnx.json", ".onnx"):
        partial = target.with_name(name + suffix + ".part")
        urllib.request.urlretrieve(base + suffix, partial, _progress)
        partial.replace(target.with_name(name + suffix))
    print(f"\nVoix « {name} » installée.")
    return target


def download_whisper(size: str, models_dir: Path) -> None:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("faster-whisper n'est pas installé : Whisper ignoré.")
        return
    from .recognizer import has_cuda, pick_size

    size = pick_size(size, "cuda" if has_cuda() else "cpu")
    print(f"Téléchargement du modèle Whisper « {size} » (quelques centaines de Mo, une seule fois)…")
    WhisperModel(size, device="cpu", compute_type="int8", download_root=str(models_dir / "whisper"))
    print("Modèle Whisper installé.")


def download_all(langs: list[str], models_dir: Path, piper_voices: dict[str, str] | None = None,
                 whisper_size: str | None = None) -> None:
    for lang in langs:
        download_model(lang, models_dir)
    if whisper_size:
        download_whisper(whisper_size, models_dir)
    for lang, name in (piper_voices or {}).items():
        if lang in langs:
            download_piper_voice(name, models_dir)
