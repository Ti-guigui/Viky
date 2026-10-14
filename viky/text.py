"""Outils de normalisation du texte reconnu."""

from __future__ import annotations

import difflib
import re
import unicodedata


def normalize(text: str) -> str:
    """Met en minuscules, retire les accents et la ponctuation.

    « Ouvre-moi l'Explorateur ! » devient « ouvre moi l explorateur ».
    """
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    text = re.sub(r"(?<![a-z0-9])\.|\.(?![a-z0-9])", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# Petits mots qu'on dit souvent avant le nom : « dis Viky », « hey Viky ».
_CALLS = {"dis", "hey", "he", "eh", "ok", "okay", "salut", "bonjour", "hello", "hi"}


def strip_wake_word(text: str, wake_words: list[str]) -> tuple[bool, str]:
    """Cherche le mot de réveil au début ou à la fin de la phrase.

    Renvoie (trouvé, reste de la phrase sans le mot de réveil).
    « dis viky ouvre chrome » -> (True, « ouvre chrome »).
    """
    words = text.split()
    wake = [normalize(w) for w in wake_words]
    for i, word in enumerate(words):
        if is_wake_word(word, wake):
            return True, " ".join(words[i + 1:])
        if word not in _CALLS:
            break
    if words and is_wake_word(words[-1], wake):
        return True, " ".join(words[:-1])
    return False, text


def is_wake_word(word: str, wake: list[str]) -> bool:
    """Accepte aussi les mots proches (« vickie », « wiki »), car la reconnaissance
    vocale ne connaît pas toujours le prénom Viky."""
    if word in wake:
        return True
    return len(word) >= 4 and bool(difflib.get_close_matches(word, wake, n=1, cutoff=0.7))
