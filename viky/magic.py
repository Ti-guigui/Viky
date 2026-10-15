"""Tout ce qu'il faut pour les tours de magie.

- un « secret » (la carte ou le mot choisi par le spectateur) chargé en cachette,
  depuis le téléphone ou par un mot-code ;
- des mots-codes : des phrases anodines qui déclenchent un effet sans que le public
  voie de commande ;
- des répliques préparées : Viky répond au public exactement ce que vous avez écrit ;
- le numéro de « voyance » où Viky devine le secret avec suspense.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .text import normalize

_RANKS = {
    "as": "A", "un": "A", "1": "A", "ace": "A", "one": "A",
    "deux": "2", "two": "2", "trois": "3", "three": "3", "quatre": "4", "four": "4",
    "cinq": "5", "five": "5", "six": "6", "sept": "7", "seven": "7", "huit": "8", "eight": "8",
    "neuf": "9", "nine": "9", "dix": "10", "ten": "10",
    "valet": "V", "jack": "V", "dame": "D", "reine": "D", "queen": "D", "roi": "R", "king": "R",
}
_RANKS.update({str(n): str(n) for n in range(2, 11)})
# Lettres envoyées par la télécommande (et figures anglaises J, Q, K)
_RANKS.update({"a": "A", "v": "V", "d": "D", "r": "R", "j": "V", "q": "D", "k": "R"})
_SUITS = {
    "coeur": "♥", "coeurs": "♥", "heart": "♥", "hearts": "♥",
    "carreau": "♦", "carreaux": "♦", "diamond": "♦", "diamonds": "♦",
    "trefle": "♣", "trefles": "♣", "club": "♣", "clubs": "♣",
    "pique": "♠", "piques": "♠", "spade": "♠", "spades": "♠",
}
_RANK_NAMES = {
    "fr": {"A": "l'as", "V": "le valet", "D": "la dame", "R": "le roi"},
    "en": {"A": "the ace", "V": "the jack", "D": "the queen", "R": "the king"},
}
_NUMBER_NAMES = {
    "fr": {"2": "deux", "3": "trois", "4": "quatre", "5": "cinq", "6": "six", "7": "sept",
           "8": "huit", "9": "neuf", "10": "dix"},
    "en": {"2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven",
           "8": "eight", "9": "nine", "10": "ten"},
}
_SUIT_NAMES = {"fr": {"♥": "cœur", "♦": "carreau", "♣": "trèfle", "♠": "pique"},
               "en": {"♥": "hearts", "♦": "diamonds", "♣": "clubs", "♠": "spades"}}


@dataclass(frozen=True)
class Card:
    rank: str  # A, 2…10, V, D, R
    suit: str  # ♥ ♦ ♣ ♠

    @property
    def red(self) -> bool:
        return self.suit in "♥♦"

    def label(self, lang: str) -> str:
        """Lettre affichée dans le coin de la carte (J/Q/K en anglais)."""
        if lang == "en":
            return {"V": "J", "D": "Q", "R": "K"}.get(self.rank, self.rank)
        return self.rank

    def spoken(self, lang: str) -> str:
        rank = _RANK_NAMES[lang].get(self.rank)
        if rank is None:
            rank = ("le " if lang == "fr" else "the ") + _NUMBER_NAMES[lang][self.rank]
        joiner = " de " if lang == "fr" else " of "
        return rank + joiner + _SUIT_NAMES[lang][self.suit]


def parse_card(text: str) -> Card | None:
    """« sept de cœur », « l'as de pique », « Queen of spades », « 10♥ » -> Card."""
    for symbol in "♥♦♣♠":
        if symbol in text:
            rank = normalize(text.replace(symbol, " "))
            rank = _RANKS.get(rank)
            return Card(rank, symbol) if rank else None
    words = [w for w in normalize(text).split() if w not in ("le", "la", "l", "the", "de", "d", "of", "du")]
    if len(words) != 2:
        return None
    rank, suit = _RANKS.get(words[0]), _SUITS.get(words[1])
    return Card(rank, suit) if rank and suit else None


@dataclass
class Code:
    phrase: str  # déjà normalisée
    effect: str  # reveler, deviner, noir, effacer, dire, afficher, charger, projeter, suivant
    value: str = ""


@dataclass
class MagicShow:
    codes: list[Code] = field(default_factory=list)
    replies: dict[str, str] = field(default_factory=dict)  # phrase normalisée -> réponse
    secret: str = ""
    stage_mode: bool = False

    @property
    def card(self) -> Card | None:
        return parse_card(self.secret) if self.secret else None

    def secret_spoken(self, lang: str) -> str:
        card = self.card
        return card.spoken(lang) if card else self.secret

    def find_code(self, text: str) -> Code | None:
        """Cherche un mot-code n'importe où dans la phrase entendue."""
        padded = f" {normalize(text)} "
        for code in self.codes:
            if f" {code.phrase} " in padded:
                return code
        return None

    def find_reply(self, text: str) -> str | None:
        padded = f" {normalize(text)} "
        for phrase, reply in self.replies.items():
            if f" {phrase} " in padded:
                return reply
        return None


STAGE_PERSONA = {
    "fr": " Tu es sur scène, devant un public, aux côtés d'un magicien. Tu es mystérieuse, "
          "théâtrale et pleine d'humour, mais toujours bienveillante. Tes réponses sont très "
          "courtes (deux ou trois phrases) et ne révèlent jamais comment fonctionne un tour.",
    "en": " You are on stage, in front of an audience, beside a magician. You are mysterious, "
          "theatrical and funny, but always kind. Your answers are very short (two or three "
          "sentences) and never reveal how a trick works.",
}

SUSPENSE = {
    "fr": ["Je me concentre…", "Je perçois une image… elle devient plus nette…"],
    "en": ["I'm concentrating…", "I can see an image… it's getting clearer…"],
}


def load_magic(data: dict) -> MagicShow:
    """Lit la section [magie] du fichier de configuration."""
    codes = [Code(normalize(c["phrase"]), normalize(c.get("effet", "reveler")).replace(" ", "_"),
                  c.get("valeur", ""))
             for c in data.get("codes", []) if c.get("phrase")]
    replies = {normalize(k): v for k, v in data.get("repliques", {}).items()}
    return MagicShow(codes=codes, replies=replies, stage_mode=bool(data.get("mode_spectacle", False)))
