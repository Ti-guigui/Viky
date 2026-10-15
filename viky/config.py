"""Lecture du fichier de configuration config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .magic import MagicShow, load_magic
from .text import normalize

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
DEFAULT_CONFIG = ROOT / "config.toml"


def _documents() -> Path:
    for candidate in (Path.home() / "Documents", Path.home() / "OneDrive" / "Documents"):
        if candidate.exists():
            return candidate
    return Path.home() / "Documents"


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
    file_folders: list[Path] = field(default_factory=list)
    presenter_view: bool = False
    city: str | None = None
    news_feeds: dict[str, list[str]] = field(default_factory=dict)
    news_count: int = 5
    use_local: bool = True
    local_model: str = "qwen2.5:7b"
    ollama_url: str = "http://localhost:11434"
    use_claude: bool = True
    claude_model: str = "claude-opus-5-5"
    claude_key: str | None = None
    magic: MagicShow = field(default_factory=MagicShow)
    remote: bool = True
    remote_pin: str = ""
    remote_port: int = 8765
    data_dir: Path = field(default_factory=lambda: _documents() / "Viky")


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

    files = data.get("fichiers", {})
    extra = [Path(f).expanduser() for f in files.get("dossiers", [])]
    if extra:
        from .files import default_folders

        config.file_folders = [f for f in extra if f.exists()] + default_folders()
    config.presenter_view = bool(data.get("projecteur", {}).get("vue_presentateur", False))

    config.city = data.get("meteo", {}).get("ville") or None
    news = data.get("actualites", {})
    config.news_count = int(news.get("nombre_de_titres", config.news_count))
    config.news_feeds = {lang: news[f"flux_{lang}"] for lang in ("fr", "en") if news.get(f"flux_{lang}")}

    ai = data.get("ia", {})
    config.use_local = bool(ai.get("ia_locale", config.use_local))
    config.local_model = ai.get("modele_local", config.local_model)
    config.ollama_url = ai.get("adresse_ollama", config.ollama_url)
    config.use_claude = bool(ai.get("claude", config.use_claude))
    config.claude_model = ai.get("modele_claude", config.claude_model)
    config.claude_key = ai.get("cle_claude") or None

    magic = data.get("magie", {})
    config.magic = load_magic(magic)
    config.remote = bool(magic.get("telecommande", config.remote))
    config.remote_pin = str(magic.get("code_pin", "") or "")
    config.remote_port = int(magic.get("port", config.remote_port))

    if config.lang not in config.listen_langs:
        config.listen_langs.insert(0, config.lang)
    return config
