"""Outils de normalisation du texte reconnu."""

from __future__ import annotations

import difflib
import unicodedata


def fold_pairs(text: str) -> list[tuple[str, str]]:
    """Découpe le texte en paires (caractère sans accent, caractère d'origine).

    Les deux versions gardent exactement la même longueur : on peut chercher une
    commande dans la version sans accents, puis recopier les mots tels qu'ils ont
    été dits (« remplace ete par été » écrit bien « été »).
    """
    text = unicodedata.normalize("NFC", text.lower()).replace("œ", "oe").replace("æ", "ae")
    pairs = []
    for char in text:
        base = unicodedata.normalize("NFKD", char)[0]
        if base == "." or (base.isascii() and base.isalnum()):
            pairs.append((base, char))
        else:
            pairs.append((" ", " "))
    # Un point ne compte que dans un mot comme « youtube.com » ou « 12.5 ».
    for i, (base, _) in enumerate(pairs):
        if base == "." and not (0 < i < len(pairs) - 1 and pairs[i - 1][0].isalnum()
                                and pairs[i + 1][0].isalnum()):
            pairs[i] = (" ", " ")
    return squash(pairs)


def squash(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Fusionne les espaces répétés et retire ceux du début et de la fin."""
    result: list[tuple[str, str]] = []
    for pair in pairs:
        if pair[0] == " " and (not result or result[-1][0] == " "):
            continue
        result.append(pair)
    while result and result[-1][0] == " ":
        result.pop()
    return result


def fold(text: str) -> tuple[str, str]:
    """Renvoie (texte sans accents, texte avec accents), en minuscules et sans ponctuation."""
    pairs = fold_pairs(text)
    return "".join(b for b, _ in pairs), "".join(c for _, c in pairs)


def normalize(text: str) -> str:
    """Met en minuscules, retire les accents et la ponctuation.

    « Ouvre-moi l'Explorateur ! » devient « ouvre moi l explorateur ».
    """
    return fold(text)[0]


def tidy(text: str) -> str:
    """Comme normalize, mais en gardant les accents : « Écris l'été » -> « écris l été »."""
    return fold(text)[1]


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
        if is_wake_word(normalize(word), wake):
            return True, " ".join(words[i + 1:])
        if normalize(word) not in _CALLS:
            break
    if words and is_wake_word(normalize(words[-1]), wake):
        return True, " ".join(words[:-1])
    return False, text


def is_wake_word(word: str, wake: list[str]) -> bool:
    """Accepte aussi les mots proches (« vickie », « wiki »), car la reconnaissance
    vocale ne connaît pas toujours le prénom Viky."""
    if word in wake:
        return True
    return len(word) >= 4 and bool(difflib.get_close_matches(word, wake, n=1, cutoff=0.7))


def find_spans(text: str, needle: str) -> list[tuple[int, int]]:
    """Positions (début, longueur) de `needle` dans `text`, sans tenir compte
    des majuscules, des accents ni de la ponctuation (« c est » trouve « C'est »)."""
    def char_fold(char: str) -> str:
        base = unicodedata.normalize("NFKD", char)[0].lower() if char else char
        return base if base.isalnum() else " "

    haystack = "".join(char_fold(c) for c in text)  # même longueur que text
    target = normalize(needle)
    if not target:
        return []
    spans, start = [], 0
    while (index := haystack.find(target, start)) != -1:
        before = haystack[index - 1] if index else " "
        after = haystack[index + len(target)] if index + len(target) < len(haystack) else " "
        if before == " " and after == " ":  # mots entiers seulement
            spans.append((index, len(target)))
        start = index + len(target)
    return spans
