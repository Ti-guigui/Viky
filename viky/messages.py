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
        "help": "Je peux ouvrir vos fichiers, présentations et tableaux, les afficher sur le projecteur, "
                "faire défiler les diapos et modifier Excel à la voix. Je donne la météo et les "
                "grands titres, je réponds à vos questions et je fais des recherches complètes. "
                "Je peux aussi ouvrir des applications et des sites, donner l'heure, régler le "
                "volume, prendre des photos et des notes, et raconter des blagues.",
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
        "not_available": "Ce n'est pas possible pour le moment : le logiciel n'est pas ouvert "
                         "ou cette fonction n'existe pas sur ce système.",
        "ok": "D'accord.",
        "no_projector": "Je ne détecte pas de projecteur. Vérifiez le câble HDMI et que l'écran est en mode étendu.",
        "projecting": "J'affiche {name} sur le projecteur.",
        "file_not_found": "Je n'ai pas trouvé de fichier qui ressemble à {name}.",
        "cell_set": "C'est fait, {cell} vaut {value}.",
        "cell_get": "La cellule {cell} contient {value}.",
        "cell_empty": "La cellule {cell} est vide.",
        "bad_cell": "Je n'ai pas compris le nom de la cellule. Dites par exemple : cellule B3.",
        "saved": "C'est enregistré.",
        "title_set": "Titre modifié.",
        "replaced": "C'est corrigé : {new} à la place de {old}.",
        "text_not_found": "Je ne trouve pas « {old} » sur cette diapo.",
        "thinking": ["Je réfléchis.", "Laissez-moi réfléchir.", "Une seconde."],
        "no_brain": "Mon intelligence artificielle n'est pas configurée. Installez Ollama ou "
                    "ajoutez une clé Claude dans le fichier de configuration.",
        "no_claude": "Pour les recherches complètes, il me faut une clé Claude dans le fichier de configuration.",
        "offline": "Je n'arrive pas à joindre internet pour le moment.",
        "place_not_found": "Je ne trouve pas cet endroit.",
        "news_intro": "Voici les grands titres.",
        "news_outro": "Dites par exemple « approfondis le numéro deux » pour en savoir plus.",
        "news_bad_number": "Je n'ai que {count} titres. Choisissez un numéro entre 1 et {count}.",
        "research_start": "Je lance une recherche complète sur {query}. Cela peut prendre une minute.",
        "research_saved": "Le rapport détaillé est enregistré. Dites « affiche le rapport » pour le voir, "
                          "ou « projette le rapport » pour le montrer au public.",
        "no_report": "Je n'ai pas encore fait de recherche.",
        "name_set": "Enchantée, {name}. Je m'en souviendrai.",
        "remembered": "C'est noté, je m'en souviendrai.",
        "memory_empty": "Je ne sais encore rien sur vous. Dites par exemple : souviens-toi que j'aime le jazz.",
        "recall_name": "Vous vous appelez {name}.",
        "forgotten": "C'est fait, j'ai tout oublié.",
        "bad_duration": "Je n'ai pas compris la durée. Dites par exemple : minuteur de 5 minutes.",
        "timer_set": "Minuteur de {duration} lancé.",
        "timer_done": "Le minuteur de {duration} est terminé !",
        "remind_when": "Pour quand ? Dites par exemple : rappelle-moi d'appeler Paul à 18 heures, ou dans 10 minutes.",
        "reminder_set": "C'est noté, je vous rappellerai {when} : {what}.",
        "reminder_due": "Rappel : {what}.",
        "no_reminders": "Vous n'avez aucun rappel.",
        "reminders_intro": "Vous avez {count} rappel(s).",
        "reminders_cleared": "Tous les rappels sont supprimés.",
        "briefing_hello_morning": "Bonjour.",
        "briefing_hello_evening": "Bonsoir.",
        "briefing_news": "Côté actualité :",
        "briefing_end": "Je suis à votre disposition.",
        "status_battery": "Batterie à {battery} %.",
        "status_battery_plugged": "Batterie à {battery} %, en charge.",
        "status_load": "Processeur à {cpu} %, mémoire utilisée à {ram} %.",
        "wifi_on": "Vous êtes connecté au réseau {name}.",
        "wifi_off": "Vous n'êtes connecté à aucun réseau Wi-Fi.",
        "brightness": "Luminosité à {level} %.",
        "confirm_shutdown": "Voulez-vous vraiment éteindre l'ordinateur ? Dites « confirme » ou « annule ».",
        "confirm_restart": "Voulez-vous vraiment redémarrer l'ordinateur ? Dites « confirme » ou « annule ».",
        "confirm_sleep": "Je mets l'ordinateur en veille ? Dites « confirme » ou « annule ».",
        "doing_shutdown": "Arrêt de l'ordinateur dans 15 secondes. Dites « annule » pour l'empêcher.",
        "doing_restart": "Redémarrage dans 15 secondes. Dites « annule » pour l'empêcher.",
        "doing_sleep": "Mise en veille. À tout à l'heure.",
        "cancelled": "D'accord, j'annule.",
        "power_cancelled": "Arrêt annulé.",
        "stage_on": "Mode spectacle activé. Que la magie commence.",
        "stage_off": "Retour au mode normal.",
        "guess_blurry": "Mes visions sont troubles ce soir… Concentrez-vous plus fort.",
        "guess_reveal": "Je vois… {secret} !",
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
        "help": "I can open your files, slides and spreadsheets, show them on the projector, "
                "move through slides and edit Excel by voice. I give the weather and the headlines, "
                "answer your questions and do full research. I can also open apps and websites, "
                "tell the time, change the volume, take photos and notes, and tell jokes.",
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
        "not_available": "That's not possible right now: the program isn't open or this "
                         "feature doesn't exist on this system.",
        "ok": "Okay.",
        "no_projector": "I can't find a projector. Check the HDMI cable and that the display is extended.",
        "projecting": "Showing {name} on the projector.",
        "file_not_found": "I couldn't find a file like {name}.",
        "cell_set": "Done, {cell} is now {value}.",
        "cell_get": "Cell {cell} contains {value}.",
        "cell_empty": "Cell {cell} is empty.",
        "bad_cell": "I didn't get the cell name. Say for example: cell B3.",
        "saved": "Saved.",
        "title_set": "Title changed.",
        "replaced": "Fixed: {new} instead of {old}.",
        "text_not_found": "I can't find \"{old}\" on this slide.",
        "thinking": ["Let me think.", "One second.", "Thinking."],
        "no_brain": "My artificial intelligence isn't set up. Install Ollama or add a Claude key "
                    "to the configuration file.",
        "no_claude": "For full research I need a Claude key in the configuration file.",
        "offline": "I can't reach the internet right now.",
        "place_not_found": "I can't find that place.",
        "news_intro": "Here are the headlines.",
        "news_outro": "Say for example \"tell me more about number two\" to hear more.",
        "news_bad_number": "I only have {count} headlines. Pick a number between 1 and {count}.",
        "research_start": "Starting full research on {query}. This can take a minute.",
        "research_saved": "The detailed report is saved. Say \"show the report\" to see it, "
                          "or \"show the report on the projector\" for the audience.",
        "no_report": "I haven't done any research yet.",
        "name_set": "Nice to meet you, {name}. I'll remember that.",
        "remembered": "Got it, I'll remember that.",
        "memory_empty": "I don't know anything about you yet. Say for example: remember that I like jazz.",
        "recall_name": "Your name is {name}.",
        "forgotten": "Done, I've forgotten everything.",
        "bad_duration": "I didn't get the duration. Say for example: set a timer for 5 minutes.",
        "timer_set": "Timer set for {duration}.",
        "timer_done": "Your {duration} timer is done!",
        "remind_when": "When? Say for example: remind me to call Paul at 6 pm, or in 10 minutes.",
        "reminder_set": "Got it, I'll remind you {when}: {what}.",
        "reminder_due": "Reminder: {what}.",
        "no_reminders": "You have no reminders.",
        "reminders_intro": "You have {count} reminder(s).",
        "reminders_cleared": "All reminders deleted.",
        "briefing_hello_morning": "Good morning.",
        "briefing_hello_evening": "Good evening.",
        "briefing_news": "In the news:",
        "briefing_end": "I'm at your service.",
        "status_battery": "Battery at {battery}%.",
        "status_battery_plugged": "Battery at {battery}%, charging.",
        "status_load": "CPU at {cpu}%, memory at {ram}%.",
        "wifi_on": "You're connected to {name}.",
        "wifi_off": "You're not connected to any Wi-Fi network.",
        "brightness": "Brightness at {level}%.",
        "confirm_shutdown": "Do you really want to shut down the computer? Say confirm or cancel.",
        "confirm_restart": "Do you really want to restart the computer? Say confirm or cancel.",
        "confirm_sleep": "Put the computer to sleep? Say confirm or cancel.",
        "doing_shutdown": "Shutting down in 15 seconds. Say cancel to stop it.",
        "doing_restart": "Restarting in 15 seconds. Say cancel to stop it.",
        "doing_sleep": "Going to sleep. See you soon.",
        "cancelled": "Okay, cancelled.",
        "power_cancelled": "Shutdown cancelled.",
        "stage_on": "Show mode on. Let the magic begin.",
        "stage_off": "Back to normal mode.",
        "guess_blurry": "My visions are blurry tonight… Concentrate harder.",
        "guess_reveal": "I see… {secret}!",
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
        hours = {0: "minuit", 12: "midi", 1: "une heure", 13: "13 heures"}.get(now.hour, f"{now.hour} heures")
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
