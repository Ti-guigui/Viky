"""Mémoire à long terme : ce que Viky sait de vous (prénom, préférences, faits)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class Memory:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.name: str | None = None
        self.facts: list[dict] = []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.name = data.get("prenom")
            self.facts = data.get("faits", [])
        except (OSError, ValueError):
            pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"prenom": self.name, "faits": self.facts},
                                        ensure_ascii=False, indent=1), encoding="utf-8")

    def set_name(self, name: str) -> None:
        self.name = name.strip()[:40].title()
        self._save()

    def remember(self, fact: str) -> None:
        fact = fact.strip()
        if fact and fact not in (f["texte"] for f in self.facts):
            self.facts.append({"texte": fact, "date": f"{datetime.now():%Y-%m-%d}"})
            self.facts = self.facts[-200:]
            self._save()

    def forget_all(self) -> None:
        self.name = None
        self.facts = []
        self._save()

    def context(self, lang: str) -> str:
        """Texte ajouté aux consignes de l'IA pour qu'elle tienne compte de vous."""
        if not self.name and not self.facts:
            return ""
        if lang == "fr":
            lines = [f"L'utilisateur s'appelle {self.name}." if self.name else ""]
            if self.facts:
                lines.append("Ce que tu sais de lui : " + " ; ".join(f["texte"] for f in self.facts[-40:]) + ".")
        else:
            lines = [f"The user's name is {self.name}." if self.name else ""]
            if self.facts:
                lines.append("What you know about them: " + "; ".join(f["texte"] for f in self.facts[-40:]) + ".")
        return " " + " ".join(line for line in lines if line)
