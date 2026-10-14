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


def download_all(langs: list[str], models_dir: Path) -> None:
    for lang in langs:
        download_model(lang, models_dir)
