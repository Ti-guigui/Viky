"""Lecture du fichier de configuration config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .text import normalize

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
DEFAULT_CONFIG = ROOT / "config.toml"


@dataclass
class Config:
    lang: str = "fr"
    listen_langs: list[str] = field(default_factory=lambda: ["fr", "en"])
    wake_words: list[str] = field(default_factory=lambda: [
        "viky", "vicky", "vicki", "viki", "vikki", "mickey", "mikey", "wiki"])
    awake_seconds: float = 8.0
    double_clap: bool = True
    clap_sensitivity: float = 0.5
    voice_rate: int = 180
    apps: dict[str, str] = field(default_factory=dict)
    sites: dict[str, str] = field(default_factory=dict)


def load_config(path: Path | None = None) -> Config:
    config = Config()
    path = path or DEFAULT_CONFIG
    if not path.exists():
        return config
    with open(path, "rb") as f:
        data = tomllib.load(f)

    general = data.get("general", {})
    config.lang = general.get("langue", config.lang)
    config.listen_langs = general.get("langues_ecoute", config.listen_langs)
    config.wake_words = general.get("mots_de_reveil", config.wake_words)
    config.awake_seconds = float(general.get("duree_eveil", config.awake_seconds))
    config.double_clap = bool(general.get("double_clap", config.double_clap))
    config.clap_sensitivity = float(general.get("sensibilite_clap", config.clap_sensitivity))
    config.voice_rate = int(general.get("vitesse_voix", config.voice_rate))
    config.apps = {normalize(k): v for k, v in data.get("applications", {}).items()}
    config.sites = {normalize(k): v for k, v in data.get("sites", {}).items()}

    if config.lang not in config.listen_langs:
        config.listen_langs.insert(0, config.lang)
    return config
