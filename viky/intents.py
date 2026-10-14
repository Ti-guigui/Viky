"""Compréhension des commandes : transforme une phrase en intention."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .text import normalize


@dataclass
class Intent:
    name: str
    lang: str
    args: dict[str, str] = field(default_factory=dict)


_FILLERS = {
    "fr": r"\b(s il te plait|s il vous plait|est ce que tu peux|est ce que tu pourrais|"
          r"tu peux|tu pourrais|peux tu|pourrais tu|j aimerais que tu|je veux que tu|"
          r"je voudrais que tu|stp|svp)\b",
    "en": r"\b(please|can you|could you|would you|will you|i want you to|i d like you to)\b",
}

# L'ordre compte : la première règle qui correspond l'emporte.
# Les commandes « verbe + complément » passent avant les mots-clés,
# pour que « cherche la date de noël » soit une recherche et pas la date.
_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "fr": [
        ("quit", r"^(arrete toi|au revoir|eteins toi|bonne nuit|quitte toi|ferme toi|desactive toi)$"),
        ("thanks", r"^(merci( beaucoup| bien)?|c est gentil)$"),
        ("greet", r"^(bonjour|salut|coucou|bonsoir|hello)$"),
        ("lang_en", r"^(parle|passe|reponds)( moi)? en anglais$"),
        ("lang_fr", r"^(parle|passe|reponds)( moi)? en francais$"),
        ("youtube", r"^(mets|joue|lance|cherche|mettre|jouer) (?P<query>.+) sur youtube$"),
        ("search", r"^(cherche|recherche|google|chercher|rechercher)"
                   r"( sur (internet|google|le web))? (?P<query>.+)$"),
        ("note", r"^(note|prends note|prends en note|ecris|retiens)( que| de)? (?P<text>.+)$"),
        ("whoami", r"(qui es tu|tu es qui|comment tu t appelles|ton nom|presente toi)"),
        ("help", r"(^aide( moi)?$|que sais tu faire|qu est ce que tu sais faire|"
                 r"qu est ce que tu peux faire|tes commandes)"),
        ("time", r"(quelle heure|l heure qu il est|donne moi l heure|^l heure$)"),
        ("date", r"(quel jour|quelle date|la date|on est le combien)"),
        ("joke", r"(blague|fais moi rire)"),
        ("vol_up", r"((monte|augmente|hausse) (le )?(son|volume)|plus fort)"),
        ("vol_down", r"((baisse|diminue|descends) (le )?(son|volume)|moins fort)"),
        ("mute", r"(coupe (le )?son|sourdine|\bsilence\b|\bmute\b)"),
        ("lock", r"verrouille"),
        ("screenshot", r"capture (d |l )?ecran"),
        ("photo", r"((prends|prend|prendre|fais) (moi )?une photo|selfie)"),
        ("close", r"^(ferme|quitte|fermer) (?P<target>.+)$"),
        ("open", r"^(ouvre|ouvrir|lance|lancer|demarre|demarrer|va sur|affiche|montre)( moi)? (?P<target>.+)$"),
    ],
    "en": [
        ("quit", r"^(stop listening|goodbye|bye|shut down|turn off|go to sleep|exit|quit)$"),
        ("thanks", r"^(thank you|thanks)( very much| a lot)?$"),
        ("greet", r"^(hello|hi|hey|good (morning|evening|afternoon))$"),
        ("lang_fr", r"^(speak|switch to|answer in|talk in) french$"),
        ("lang_en", r"^(speak|switch to|answer in|talk in) english$"),
        ("youtube", r"^(play|put on|search|search for) (?P<query>.+) on youtube$"),
        ("search", r"^(search|google|look up)( for| the web for| online for)? (?P<query>.+)$"),
        ("note", r"^(take a note|note|write down|remember)( that)? (?P<text>.+)$"),
        ("whoami", r"(who are you|what is your name|what s your name|introduce yourself)"),
        ("help", r"(^help( me)?$|what can you do|your commands)"),
        ("time", r"(what time|the time)"),
        ("date", r"(what day|what s the date|what is the date|today s date|the date)"),
        ("joke", r"(joke|make me laugh)"),
        ("vol_up", r"(turn (it )?up|volume up|louder|(increase|raise) (the )?volume)"),
        ("vol_down", r"(turn (it )?down|volume down|quieter|(decrease|lower) (the )?volume)"),
        ("mute", r"(\bmute\b|\bsilence\b)"),
        ("lock", r"lock (the |my )?(computer|pc|screen|session)"),
        ("screenshot", r"(screenshot|screen shot|capture (the )?screen)"),
        ("photo", r"((take|snap) a (photo|picture|selfie)|selfie)"),
        ("close", r"^(close|quit|kill) (?P<target>.+)$"),
        ("open", r"^(open|launch|start|run|go to|show me)( up)? (?P<target>.+)$"),
    ],
}

_COMPILED = {
    lang: [(name, re.compile(pattern)) for name, pattern in patterns]
    for lang, patterns in _PATTERNS.items()
}

LANGS = tuple(_PATTERNS)


def clean(text: str, lang: str) -> str:
    text = re.sub(_FILLERS[lang], " ", normalize(text))
    return re.sub(r"\s+", " ", text).strip()


def parse(text: str, lang: str) -> Intent | None:
    """Reconnaît une commande dans une langue donnée."""
    text = clean(text, lang)
    if not text:
        return None
    for name, regex in _COMPILED[lang]:
        match = regex.search(text)
        if match:
            args = {k: v.strip() for k, v in match.groupdict().items() if v}
            return Intent(name, lang, args)
    return None


def parse_any(texts: dict[str, str], order: list[str]) -> Intent | None:
    """Essaie chaque langue dans l'ordre de préférence.

    `texts` associe une langue au texte reconnu par le modèle de cette langue.
    """
    for lang in order:
        if lang in texts and lang in _COMPILED:
            intent = parse(texts[lang], lang)
            if intent:
                return intent
    return None
