import types

import pytest

from viky.assistant import Assistant
from viky.config import Config


class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text, lang):
        self.said.append((text, lang))


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


@pytest.fixture
def setup():
    calls = []
    fake = types.SimpleNamespace(
        clean_target=lambda t: t,
        resolve_target=lambda t, apps=None, sites=None: ("app", t),
        open_target=lambda t, apps, sites: calls.append(("open", t)) or True,
        close_app=lambda t, apps: calls.append(("close", t)) or False,
        web_search=lambda q: calls.append(("search", q)),
        youtube_search=lambda q: calls.append(("youtube", q)),
        volume=lambda d: calls.append(("volume", d)) or True,
        lock_screen=lambda: True,
        screenshot=lambda: None,
        take_photo=lambda: "photo.jpg",
        add_note=lambda t: calls.append(("note", t)),
    )
    speaker, clock = FakeSpeaker(), Clock()
    return Assistant(Config(), speaker, fake, files=FakeFiles(), clock=clock), speaker, calls, clock


class FakeFiles:
    def find(self, spoken):
        return None


def test_ignored_without_wake_word(setup):
    viky, speaker, calls, _ = setup
    assert viky.on_utterance({"fr": "ouvre chrome", "en": "of rome"})
    assert calls == [] and speaker.said == []


def test_wake_word_and_command(setup):
    viky, speaker, calls, _ = setup
    viky.on_utterance({"fr": "vicky ouvre chrome", "en": "vicky of rome"})
    assert calls == [("open", "chrome")]
    assert speaker.said == [("J'ouvre chrome.", "fr")]


def test_wake_word_alone_then_command(setup):
    viky, speaker, calls, clock = setup
    viky.on_utterance({"fr": "viky", "en": "vicky"})
    assert speaker.said[-1][0] in ["Oui ?", "Je vous écoute.", "Oui, que puis-je faire ?"]
    clock.now += 3
    viky.on_utterance({"fr": "monte le son", "en": "month the song"})
    assert calls == [("volume", "up")]


def test_falls_asleep(setup):
    viky, _, calls, clock = setup
    viky.on_utterance({"fr": "viky", "en": ""})
    clock.now += 30
    viky.on_utterance({"fr": "monte le son", "en": ""})
    assert calls == []


def test_english_command_answered_in_english(setup):
    viky, speaker, calls, _ = setup
    viky.on_utterance({"fr": "vicky au revoir sur youtube", "en": "vicky play jazz on youtube"})
    assert ("youtube", "jazz") in calls
    assert speaker.said[-1] == ("Searching YouTube for jazz.", "en")


def test_failures_are_reported(setup):
    viky, speaker, _, _ = setup
    viky.on_utterance({"fr": "ferme spotify"}, require_wake=False)
    viky.on_utterance({"fr": "capture d'écran"}, require_wake=False)
    assert [t for t, _ in speaker.said] == ["Je n'ai pas réussi à fermer spotify.",
                                             "Désolée, ça n'a pas fonctionné."]


def test_not_understood(setup):
    viky, speaker, _, _ = setup
    viky.on_utterance({"fr": "viky le chat dort"})
    assert speaker.said == [("Désolée, je n'ai pas compris.", "fr")]


def test_switch_language(setup):
    viky, speaker, _, _ = setup
    viky.on_utterance({"fr": "parle en anglais"}, require_wake=False)
    assert viky.lang == "en"
    assert speaker.said[-1] == ("Okay, I'll speak English.", "en")


def test_quit(setup):
    viky, speaker, _, _ = setup
    assert viky.on_utterance({"fr": "au revoir"}, require_wake=False) is False
    assert speaker.said == [("Au revoir !", "fr")]
