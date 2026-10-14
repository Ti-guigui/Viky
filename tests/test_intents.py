import pytest

from viky.intents import parse, parse_any


@pytest.mark.parametrize("text, name, args", [
    ("Ouvre Google Chrome", "open", {"target": "google chrome"}),
    ("Est-ce que tu peux ouvrir le bloc-notes s'il te plaît ?", "open", {"target": "le bloc notes"}),
    ("Lance-moi la calculatrice", "open", {"target": "la calculatrice"}),
    ("Va sur youtube point com", "open", {"target": "youtube point com"}),
    ("Ferme Chrome", "close", {"target": "chrome"}),
    ("Cherche la recette des crêpes", "search", {"query": "la recette des crepes"}),
    ("Cherche sur internet la date de Noël", "search", {"query": "la date de noel"}),
    ("Mets Aya Nakamura sur YouTube", "youtube", {"query": "aya nakamura"}),
    ("Quelle heure est-il ?", "time", {}),
    ("On est quel jour ?", "date", {}),
    ("Raconte-moi une blague", "joke", {}),
    ("Monte le son", "vol_up", {}),
    ("Baisse le volume", "vol_down", {}),
    ("Coupe le son", "mute", {}),
    ("Verrouille l'ordinateur", "lock", {}),
    ("Fais une capture d'écran", "screenshot", {}),
    ("Prends une photo", "photo", {}),
    ("Note que je dois acheter du pain", "note", {"text": "je dois acheter du pain"}),
    ("Qui es-tu ?", "whoami", {}),
    ("Qu'est-ce que tu sais faire ?", "help", {}),
    ("Merci beaucoup", "thanks", {}),
    ("Bonjour", "greet", {}),
    ("Au revoir", "quit", {}),
    ("Parle en anglais", "lang_en", {}),
])
def test_french(text, name, args):
    intent = parse(text, "fr")
    assert intent is not None, text
    assert (intent.name, intent.args) == (name, args)


@pytest.mark.parametrize("text, name, args", [
    ("Open Google Chrome", "open", {"target": "google chrome"}),
    ("Can you please launch the calculator", "open", {"target": "the calculator"}),
    ("Close Spotify", "close", {"target": "spotify"}),
    ("Search for the weather in Paris", "search", {"query": "the weather in paris"}),
    ("Play lofi music on YouTube", "youtube", {"query": "lofi music"}),
    ("What time is it?", "time", {}),
    ("What's the date today?", "date", {}),
    ("Tell me a joke", "joke", {}),
    ("Turn the volume up", "vol_up", {}),
    ("Lock the computer", "lock", {}),
    ("Take a screenshot", "screenshot", {}),
    ("Take a picture", "photo", {}),
    ("Take a note that the meeting is at 3", "note", {"text": "the meeting is at 3"}),
    ("Goodbye", "quit", {}),
    ("Speak French", "lang_fr", {}),
])
def test_english(text, name, args):
    intent = parse(text, "en")
    assert intent is not None, text
    assert (intent.name, intent.args) == (name, args)


def test_unknown_sentence():
    assert parse("le chat dort sur le canapé", "fr") is None


def test_french_is_preferred():
    intent = parse_any({"fr": "ouvre chrome", "en": "open chrome"}, ["fr", "en"])
    assert intent.lang == "fr"


def test_falls_back_to_english():
    intent = parse_any({"fr": "au pain chrome", "en": "open chrome"}, ["fr", "en"])
    assert (intent.name, intent.lang) == ("open", "en")
