"""Retrouve un fichier (PDF, PowerPoint, Excel…) à partir de son nom prononcé."""

from __future__ import annotations

import difflib
import os
import re
import time
from pathlib import Path

from .text import normalize

EXTENSIONS = {
    "ppt": {".pptx", ".ppt", ".ppsx", ".pps", ".pptm", ".odp"},
    "pdf": {".pdf"},
    "xls": {".xlsx", ".xlsm", ".xls", ".csv", ".ods"},
    "doc": {".docx", ".doc", ".odt", ".rtf", ".txt"},
    "img": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"},
    "vid": {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v"},
}
ALL_EXTENSIONS = set().union(*EXTENSIONS.values())

# Mots qui précisent le type de fichier recherché.
KIND_WORDS = [
    (r"(presentation|diaporama|powerpoint|power point|diapos?|slides?|slideshow)", "ppt"),
    (r"pdf", "pdf"),
    (r"(tableau|tableur|excel|classeur|feuille de calcul|spreadsheet|workbook)", "xls"),
    (r"(document|word|texte|text)", "doc"),
    (r"(photo|image|picture|photos|images|pictures)", "img"),
    (r"(video|videos|film|movie)", "vid"),
    (r"(fichier|file)", None),
]
_LEADING = re.compile(r"^(le|la|l|les|mon|ma|mes|un|une|du|de|des|d|the|my|a|called|appele|appelee|nomme|nommee|sur|about|of)\s+")
_LATEST = {"dernier", "derniere", "recent", "recente", "last", "latest", "newest"}
_SKIPPED_DIRS = {"node_modules", "appdata", "$recycle.bin", "windows", "program files", "__pycache__"}


def split_kind(spoken: str) -> tuple[str | None, str]:
    """« la présentation du mariage » -> (« ppt », « mariage »)."""
    text = normalize(spoken)
    kind = None
    for pattern, value in KIND_WORDS:
        regex = re.compile(rf"\b{pattern}\b")
        if regex.search(text):
            if kind is None:
                kind = value
            text = regex.sub(" ", text, count=1)
            break
    text = re.sub(r"\s+", " ", text).strip()
    previous = None
    while previous != text:
        previous = text
        text = _LEADING.sub("", text)
    return kind, text


def file_key(path: Path) -> str:
    return normalize(re.sub(r"[_\-.]+", " ", path.stem))


def _score(name: str, key: str) -> float:
    if name == key:
        return 1.0
    words, key_words = name.split(), key.split()
    if words and all(w in key_words for w in words):
        return 0.9 - 0.01 * (len(key_words) - len(words))
    if name in key:
        return 0.8
    return difflib.SequenceMatcher(None, name, key).ratio()


def best_match(spoken: str, files: list[Path]) -> Path | None:
    kind, name = split_kind(spoken)
    if kind:
        files = [f for f in files if f.suffix.lower() in EXTENSIONS[kind]]
    if not files:
        return None
    if not name or name in _LATEST:
        return max(files, key=_mtime) if (kind or name) else None
    scored = [(_score(name, file_key(f)), _mtime(f), f) for f in files]
    score, _, path = max(scored, key=lambda item: (round(item[0], 3), item[1]))
    return path if score >= 0.65 else None


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def default_folders() -> list[Path]:
    home = Path.home()
    names = ["Desktop", "Documents", "Downloads", "Pictures", "Videos", "Movies"]
    folders = [home / n for n in names] + [home / "OneDrive" / n for n in names]
    return [f for f in folders if f.exists()]


class FileIndex:
    """Liste les fichiers utiles des dossiers personnels, rafraîchie toutes les 2 minutes."""

    def __init__(self, folders: list[Path] | None = None, max_depth: int = 4, ttl: float = 120) -> None:
        self.folders = folders if folders is not None else default_folders()
        self.max_depth = max_depth
        self.ttl = ttl
        self.files: list[Path] = []
        self.updated = 0.0

    def refresh(self) -> None:
        found: list[Path] = []
        for root_folder in self.folders:
            root_depth = len(Path(root_folder).parts)
            for current, dirs, names in os.walk(root_folder):
                depth = len(Path(current).parts) - root_depth
                dirs[:] = [d for d in dirs if not d.startswith((".", "~"))
                           and d.lower() not in _SKIPPED_DIRS and depth < self.max_depth]
                for name in names:
                    if not name.startswith(("~$", ".")) and Path(name).suffix.lower() in ALL_EXTENSIONS:
                        found.append(Path(current) / name)
        self.files = found
        self.updated = time.monotonic()

    def find(self, spoken: str) -> Path | None:
        if time.monotonic() - self.updated > self.ttl or not self.files:
            self.refresh()
        match = best_match(spoken, self.files)
        if match is None or not match.exists():
            self.refresh()
            match = best_match(spoken, self.files)
        return match


def kind_of(path: Path) -> str | None:
    suffix = path.suffix.lower()
    for kind, extensions in EXTENSIONS.items():
        if suffix in extensions:
            return kind
    return None
