"""Nombres dits à voix haute : « vingt et un » -> 21, « b trois » -> B3."""

from __future__ import annotations

import re

from .text import normalize

_FR = {
    "zero": 0, "un": 1, "une": 1, "premier": 1, "premiere": 1, "deux": 2, "deuxieme": 2,
    "second": 2, "seconde": 2, "trois": 3, "troisieme": 3, "quatre": 4, "quatrieme": 4,
    "cinq": 5, "cinquieme": 5, "six": 6, "sixieme": 6, "sept": 7, "septieme": 7,
    "huit": 8, "huitieme": 8, "neuf": 9, "neuvieme": 9, "dix": 10, "dixieme": 10,
    "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16,
    "vingt": 20, "vingts": 20, "vingtieme": 20, "trente": 30, "quarante": 40,
    "cinquante": 50, "soixante": 60, "cent": 100, "cents": 100, "mille": 1000,
}
_EN = {
    "zero": 0, "one": 1, "first": 1, "two": 2, "second": 2, "three": 3, "third": 3,
    "four": 4, "fourth": 4, "five": 5, "fifth": 5, "six": 6, "sixth": 6, "seven": 7,
    "seventh": 7, "eight": 8, "eighth": 8, "nine": 9, "ninth": 9, "ten": 10, "tenth": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
    "ninety": 90, "hundred": 100, "thousand": 1000,
}
_WORDS = {**_EN, **_FR}
_IGNORED = {"et", "and", "numero", "number", "la", "le", "l", "n"}


def parse_number(text: str) -> int | None:
    """Convertit « 12 », « douze », « quatre vingt dix sept » ou « troisième » en entier."""
    words = [w for w in normalize(text).split() if w not in _IGNORED]
    if not words:
        return None
    if len(words) == 1:
        match = re.fullmatch(r"(\d+)(e|eme|er|ere|st|nd|rd|th)?", words[0])
        if match:
            return int(match.group(1))
    if len(words) > 1 and any(w.isdigit() for w in words):
        return None  # « 12 5 » est ambigu (12,5 ? 125 ?)
    total, current, previous = 0, 0, None
    for word in words:
        if word.isdigit():
            current += int(word)
            previous = None
            continue
        value = _WORDS.get(word)
        if value is None:
            return None
        if value == 100:
            current = (current or 1) * 100
        elif value == 1000:
            total += (current or 1) * 1000
            current = 0
        elif value == 20 and previous == 4:  # quatre vingt
            current += 80 - 4
        else:
            current += value
        previous = value
    return total + current


def parse_value(text: str) -> float | int | str:
    """Valeur à écrire dans Excel : un nombre si c'en est un, sinon le texte tel quel."""
    text = text.strip()
    if re.fullmatch(r"-?\d+([.,]\d+)?", text):
        number = float(text.replace(",", "."))
        return int(number) if number.is_integer() and "," not in text and "." not in text else number
    negative = False
    words = text.split()
    if words and words[0] in ("moins", "minus"):
        negative, text = True, " ".join(words[1:])
    for separator in (" virgule ", " point "):
        if separator in f" {text} ":
            whole, _, decimals = text.partition(separator.strip())
            a, b = parse_number(whole), parse_number(decimals)
            digits = decimals.strip()
            if a is not None and b is not None:
                value = float(f"{a}.{digits if digits.isdigit() else b}")
                return -value if negative else value
    number = parse_number(text)
    if number is not None:
        return -number if negative else number
    try:
        value = float(text.replace(",", "."))
        return -value if negative else value
    except ValueError:
        return f"-{text}" if negative else text


# Noms des lettres tels que la reconnaissance vocale peut les écrire.
_LETTERS = {
    "a": "A", "ah": "A", "b": "B", "be": "B", "bee": "B", "c": "C", "ce": "C", "se": "C",
    "ces": "C", "see": "C", "d": "D", "de": "D", "dee": "D", "e": "E", "eu": "E", "euh": "E",
    "f": "F", "effe": "F", "ef": "F", "g": "G", "ge": "G", "gee": "G", "h": "H", "hache": "H",
    "ache": "H", "i": "I", "j": "J", "ji": "J", "jay": "J", "k": "K", "ka": "K", "kay": "K",
    "l": "L", "el": "L", "elle": "L", "m": "M", "em": "M", "emme": "M", "n": "N", "enne": "N",
    "o": "O", "oh": "O", "eau": "O", "p": "P", "pe": "P", "pee": "P", "q": "Q", "cu": "Q",
    "r": "R", "air": "R", "erre": "R", "s": "S", "esse": "S", "es": "S", "t": "T", "te": "T",
    "tee": "T", "u": "U", "v": "V", "ve": "V", "vee": "V", "w": "W", "x": "X", "ix": "X",
    "y": "Y", "z": "Z", "zed": "Z", "zede": "Z",
}


def parse_cell(text: str) -> str | None:
    """« b3 », « b 3 », « bé trois », « a a douze » -> « B3 », « B3 », « B3 », « AA12 »."""
    text = normalize(text)
    compact = text.replace(" ", "")
    match = re.fullmatch(r"([a-z]{1,3})(\d+)", compact)
    if match:
        return match.group(1).upper() + match.group(2)
    words = text.split()
    letters = ""
    while words and len(letters) < 3:
        word = words[0]
        glued = re.fullmatch(r"([a-z])(\d+)", word)
        if glued:
            letters += glued.group(1).upper()
            words[0] = glued.group(2)
            break
        if word not in _LETTERS:
            break
        letters += _LETTERS[word]
        words.pop(0)
    row = parse_number(" ".join(words)) if words else None
    if not letters or not row:
        return None
    return f"{letters}{row}"
