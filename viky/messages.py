"""Phrases prononcées par Viky, en français et en anglais."""

from __future__ import annotations

import random
from datetime import datetime

MESSAGES: dict[str, dict] = {
    "fr": {
        "ready": "Bonjour, je suis Viky. Dites « Viky » ou tapez deux fois dans vos mains pour me réveiller.",
        "ready_text": "Bonjour, je suis Viky. Tapez une commande, ou « au revoir » pour quitter.",
        "yes": ["Oui ?", "Je vous écoute.", "Oui, que puis-je faire ?"],
        "not_understood": "Désolée, je n'ai pas compris.",
        "bye": "Au revoir !",
        "thanks": ["Avec plaisir !", "De rien !", "Je vous en prie."],
        "greet": ["Bonjour !", "Salut ! Que puis-je faire pour vous ?"],
        "whoami": "Je suis Viky, votre assistante vocale. Je fonctionne entièrement hors ligne, "
                  "sur votre ordinateur.",
        "help": "Je peux ouvrir des applications, des sites et des dossiers, chercher sur internet "
                "ou sur YouTube, donner l'heure et la date, régler le volume, prendre une photo ou "
                "une capture d'écran, prendre des notes, verrouiller l'ordinateur et raconter des blagues.",
        "opening": "J'ouvre {name}.",
        "open_failed": "Je n'ai pas trouvé {name}.",
        "closing": "Je ferme {name}.",
        "close_failed": "Je n'ai pas réussi à fermer {name}.",
        "searching": "Je cherche {query}.",
        "youtube": "Je cherche {query} sur YouTube.",
        "vol_up": "Je monte le son.",
        "vol_down": "Je baisse le son.",
        "mute": "D'accord.",
        "lock": "Je verrouille l'ordinateur.",
        "screenshot": "Capture d'écran enregistrée dans vos images.",
        "smile": "Souriez !",
        "photo": "Photo enregistrée dans vos images.",
        "note": "C'est noté.",
        "lang": "D'accord, je parle français.",
        "failed": "Désolée, ça n'a pas fonctionné.",
        "jokes": [
            "Pourquoi les plongeurs plongent-ils toujours en arrière ? "
            "Parce que sinon, ils tombent dans le bateau.",
            "Que dit une imprimante dans l'eau ? J'ai papier.",
            "Qu'est-ce qu'un crocodile qui surveille la pharmacie ? Un Lacoste garde.",
            "Pourquoi les ordinateurs n'ont jamais froid ? Parce qu'ils ont plein de fenêtres.",
        ],
        "weekdays": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
        "months": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
                   "septembre", "octobre", "novembre", "décembre"],
    },
    "en": {
        "ready": "Hello, I'm Viky. Say \"Viky\" or clap twice to wake me up.",
        "ready_text": "Hello, I'm Viky. Type a command, or \"goodbye\" to quit.",
        "yes": ["Yes?", "I'm listening.", "Yes, what can I do?"],
        "not_understood": "Sorry, I didn't understand.",
        "bye": "Goodbye!",
        "thanks": ["You're welcome!", "My pleasure!"],
        "greet": ["Hello!", "Hi! What can I do for you?"],
        "whoami": "I'm Viky, your voice assistant. I run entirely offline, on your computer.",
        "help": "I can open apps, websites and folders, search the web or YouTube, tell the time "
                "and date, change the volume, take a photo or a screenshot, take notes, lock the "
                "computer and tell jokes.",
        "opening": "Opening {name}.",
        "open_failed": "I couldn't find {name}.",
        "closing": "Closing {name}.",
        "close_failed": "I couldn't close {name}.",
        "searching": "Searching for {query}.",
        "youtube": "Searching YouTube for {query}.",
        "vol_up": "Turning the volume up.",
        "vol_down": "Turning the volume down.",
        "mute": "Okay.",
        "lock": "Locking the computer.",
        "screenshot": "Screenshot saved to your pictures.",
        "smile": "Smile!",
        "photo": "Photo saved to your pictures.",
        "note": "Noted.",
        "lang": "Okay, I'll speak English.",
        "failed": "Sorry, that didn't work.",
        "jokes": [
            "Why do programmers prefer dark mode? Because light attracts bugs.",
            "Why was the computer cold? It left its Windows open.",
            "I told my computer I needed a break. It said: no problem, I'll go to sleep.",
        ],
    },
}


def say(lang: str, key: str, **kwargs) -> str:
    """Renvoie la phrase `key` dans la langue `lang` (au hasard si plusieurs choix)."""
    value = MESSAGES[lang][key]
    if isinstance(value, list):
        value = random.choice(value)
    return value.format(**kwargs)


def time_sentence(lang: str, now: datetime) -> str:
    if lang == "fr":
        hours = "une heure" if now.hour == 1 else f"{now.hour} heures"
        minutes = f" {now.minute}" if now.minute else ""
        return f"Il est {hours}{minutes}."
    return f"It's {now.strftime('%I:%M %p').lstrip('0')}."


def date_sentence(lang: str, now: datetime) -> str:
    if lang == "fr":
        fr = MESSAGES["fr"]
        day = "1er" if now.day == 1 else str(now.day)
        return (f"Nous sommes le {fr['weekdays'][now.weekday()]} {day} "
                f"{fr['months'][now.month - 1]} {now.year}.")
    return f"Today is {now.strftime('%A, %B')} {now.day}, {now.year}."
