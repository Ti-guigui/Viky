"""Adaptation à la prononciation de l'utilisateur (accent, R difficiles à prononcer…).

Deux mécanismes :
1. Corrections apprises : pendant l'apprentissage, vous lisez des phrases connues ;
   Viky note comment elle les a entendues (« wappelle » au lieu de « rappelle ») et
   remplace ensuite automatiquement ces mots.
2. Rapprochement phonétique : si une phrase n'est pas comprise, Viky compare chaque
   mot à son vocabulaire de commandes en ignorant les R (et quelques autres sons
   souvent déformés), puis réessaie.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from .text import fold_pairs, normalize

# Petits mots trop courants pour être « corrigés » globalement
_STOPWORDS = {"le", "la", "les", "l", "un", "une", "de", "des", "du", "d", "a", "au", "et", "en", "je", "j",
              "tu", "il", "elle", "me", "moi", "te", "se", "ce", "ca", "qu", "que", "qui", "y", "ne", "pas",
              "the", "a", "an", "to", "of", "and", "is", "it", "in", "on", "me", "my"}


def sound_key(word: str) -> str:
    """Clé phonétique tolérante : sans R, W, H, lettres doublées ni lettres finales muettes.

    « rappelle », « wappelle » et « appelle » donnent tous « apel ».
    """
    key = normalize(word).replace(" ", "")
    key = key.replace("gh", "").replace("qu", "k").replace("ph", "f")
    key = re.sub(r"[rwh]", "", key)
    key = re.sub(r"(.)\1+", r"\1", key)
    key = re.sub(r"(es|e|s|t|x|d)$", "", key) or key
    return key


def command_vocabulary(patterns: list[str]) -> set[str]:
    """Les mots (4 lettres ou plus) qui apparaissent dans les règles de commande."""
    words: set[str] = set()
    for pattern in patterns:
        # mots entiers seulement : « rappel+e » (expression régulière) ne donne pas « rappel »
        words.update(w for w in re.findall(r"(?<![a-z])[a-z]{4,}(?![a-z+*?{\[(])", pattern)
                     if w not in ("name", "text", "query", "target", "value", "cell", "fact", "rest", "duration"))
    return words


class Pronunciation:
    def __init__(self, path: Path | None = None, vocabulary: set[str] | None = None) -> None:
        self.path = path
        self.words: dict[str, str] = {}  # mot entendu -> mot voulu
        self.phrases: dict[str, str] = {}  # suite de mots entendue -> suite voulue
        self.vocabulary = vocabulary or set()
        self._keys = {}
        for word in sorted(self.vocabulary):
            self._keys.setdefault(sound_key(word), word)
        if path and path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.words = data.get("mots", {})
                self.phrases = data.get("expressions", {})
            except (OSError, ValueError):
                pass

    # ------------------------------------------------------------ apprentissage

    def learn(self, expected: str, heard: str) -> list[tuple[str, str]]:
        """Compare la phrase attendue et ce qui a été entendu ; renvoie les corrections apprises."""
        want, got = normalize(expected).split(), normalize(heard).split()
        learned = []
        matcher = difflib.SequenceMatcher(None, got, want, autojunk=False)
        for op, g1, g2, w1, w2 in matcher.get_opcodes():
            if op != "replace":
                continue
            wrong, right = got[g1:g2], want[w1:w2]
            if len(wrong) == len(right):
                for bad, good in zip(wrong, right):
                    if bad not in _STOPWORDS and len(bad) >= 3:
                        self.words[bad] = good
                        learned.append((bad, good))
            elif len(" ".join(wrong)) >= 4:
                self.phrases[" ".join(wrong)] = " ".join(right)
                learned.append((" ".join(wrong), " ".join(right)))
        return learned

    def save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"mots": self.words, "expressions": self.phrases},
                                            ensure_ascii=False, indent=1), encoding="utf-8")

    # ------------------------------------------------------------ correction

    def correct(self, text: str) -> str:
        """Applique les corrections apprises (en gardant les accents du reste de la phrase)."""
        if not (self.words or self.phrases):
            return text
        words = _display_words(text)
        keys = [normalize(w) for w in words]
        # expressions d'abord (les plus longues en premier)
        for wrong, right in sorted(self.phrases.items(), key=lambda item: -len(item[0])):
            size = len(wrong.split())
            i = 0
            while i + size <= len(keys):
                if " ".join(keys[i:i + size]) == wrong:
                    words[i:i + size] = [right]
                    keys[i:i + size] = [right]
                i += 1
        return " ".join(self.words.get(k, w) for w, k in zip(words, keys))

    def sound_alike(self, text: str) -> str | None:
        """Remplace les mots inconnus par le mot de commande qui « sonne » pareil (sans les R).

        Renvoie None si rien n'a changé.
        """
        words = _display_words(text)
        changed = False
        for i, word in enumerate(words):
            key = normalize(word)
            if len(key) < 4 or key in self.vocabulary:
                continue
            match = self._keys.get(sound_key(key))
            if match is None:
                close = difflib.get_close_matches(sound_key(key), list(self._keys), n=1, cutoff=0.85)
                match = self._keys[close[0]] if close else None
            if match and match != key:
                words[i] = match
                changed = True
        return " ".join(words) if changed else None


def _display_words(text: str) -> list[str]:
    return "".join(c for _, c in fold_pairs(text)).split()
