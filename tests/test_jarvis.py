import types
from datetime import datetime

import pytest

from viky.assistant import Assistant
from viky.config import Config
from viky.intents import parse
from viky.memory import Memory
from viky.reminders import Reminders, parse_clock, parse_duration, parse_reminder

NOW = datetime(2026, 10, 15, 14, 0)


@pytest.mark.parametrize("text, seconds", [
    ("10 minutes", 600), ("une heure et demie", 5400), ("1 h 30", 5400), ("90 secondes", 90),
    ("dix sept minutes", 1020), ("une demi heure", 1800), ("deux heures", 7200), ("5 min", 300),
    ("half an hour", 1800), ("bonjour", None),
])
def test_parse_duration(text, seconds):
    assert parse_duration(text) == seconds


@pytest.mark.parametrize("text, hour, minute, day", [
    ("à 18h", 18, 0, 15), ("à 18h30", 18, 30, 15), ("à dix huit heures trente", 18, 30, 15),
    ("vers 20 heures 15", 20, 15, 15), ("demain à midi", 12, 0, 16), ("at 6 pm", 18, 0, 15),
    ("à 9h", 9, 0, 16),  # 9 h est passé : demain
])
def test_parse_clock(text, hour, minute, day):
    moment = parse_clock(text, NOW)
    assert (moment.hour, moment.minute, moment.day) == (hour, minute, day)


@pytest.mark.parametrize("text, due, what", [
    ("d'appeler Paul à 18h", datetime(2026, 10, 15, 18, 0), "appeler paul"),
    ("dans 10 minutes de sortir le gâteau", datetime(2026, 10, 15, 14, 10), "sortir le gâteau"),
    ("de prendre mes médicaments demain à huit heures", datetime(2026, 10, 16, 8, 0), "prendre mes médicaments"),
    ("d'aller à la poste à dix sept heures", datetime(2026, 10, 15, 17, 0), "aller à la poste"),
    ("to call mom in 20 minutes", datetime(2026, 10, 15, 14, 20), "call mom"),
    ("d'acheter du pain", None, "acheter du pain"),
])
def test_parse_reminder(text, due, what):
    assert parse_reminder(text, NOW) == (due, what)


@pytest.mark.parametrize("text, name", [
    ("Rappelle-moi d'appeler Paul à 18h", "remind"), ("Minuteur de 5 minutes", "timer"),
    ("Lance un minuteur de dix minutes", "timer"), ("Quels sont mes rappels ?", "list_reminders"),
    ("Fais-moi le point", "briefing"), ("Appelle-moi Guillaume", "set_name"),
    ("Souviens-toi que j'aime le jazz", "remember"), ("Qu'est-ce que tu sais sur moi ?", "recall"),
    ("Éteins l'ordinateur", "shutdown"), ("Confirme", "confirm"), ("Annule", "cancel"),
    ("Niveau de batterie", "status"), ("Monte la luminosité", "brightness_up"),
    ("Mets la luminosité à 50", "brightness_set"), ("Chanson suivante", "media_next"), ("Pause", "media_pause"),
    ("Affiche le bureau", "desktop"), ("Note que le spectacle est samedi", "note"),
])
def test_intents(text, name):
    assert parse(text, "fr").name == name


def test_reminders_store(tmp_path):
    clock = [1000.0]
    store = Reminders(tmp_path / "r.json", clock=lambda: clock[0])
    store.add(1010, "a")
    store.add(1005, "b")
    assert [r.text for r in store.upcoming()] == ["b", "a"]
    clock[0] = 1006
    assert [r.text for r in store.pop_due()] == ["b"]
    assert [r.text for r in Reminders(tmp_path / "r.json").items] == ["a"]  # relu depuis le disque


def test_memory(tmp_path):
    memory = Memory(tmp_path / "m.json")
    assert memory.context("fr") == ""
    memory.set_name("guillaume")
    memory.remember("aime le jazz")
    again = Memory(tmp_path / "m.json")
    assert again.name == "Guillaume"
    assert again.context("fr") == " L'utilisateur s'appelle Guillaume. Ce que tu sais de lui : aime le jazz."


class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text, lang):
        self.said.append(text)


class FakeSystem:
    class NotSupported(Exception):
        pass

    def __init__(self):
        self.calls = []

    def status(self):
        return {"cpu": 12, "ram": 45, "battery": 82, "plugged": True}

    def power(self, action):
        self.calls.append(("power", action))

    def media(self, action):
        self.calls.append(("media", action))

    def brightness(self, change=None, level=None):
        self.calls.append(("brightness", change, level))
        return level if level is not None else 70

    def beep(self):
        self.calls.append("beep")


@pytest.fixture
def viky(tmp_path):
    speaker, system = FakeSpeaker(), FakeSystem()
    brain = types.SimpleNamespace(available=False, use_claude=False, history=[], persona=None, context=None)
    projector = types.SimpleNamespace(NotAvailable=RuntimeError)
    clock = [0.0]
    assistant = Assistant(Config(), speaker, types.SimpleNamespace(), projector, files=types.SimpleNamespace(),
                          brain=brain, stage=types.SimpleNamespace(), system=system,
                          memory=Memory(tmp_path / "m.json"), reminders=Reminders(tmp_path / "r.json"),
                          clock=lambda: clock[0])
    assistant.clock_value = clock
    return assistant, speaker, system


def say(assistant, text):
    assistant.on_utterance({"fr": text}, require_wake=False)


def test_power_needs_confirmation(viky):
    assistant, speaker, system = viky
    say(assistant, "éteins l'ordinateur")
    assert system.calls == [] and "Voulez-vous vraiment éteindre" in speaker.said[-1]
    say(assistant, "confirme")
    assert system.calls == [("power", "shutdown")]
    say(assistant, "annule")
    assert system.calls[-1] == ("power", "cancel")


def test_power_confirmation_expires(viky):
    assistant, speaker, system = viky
    say(assistant, "redémarre le pc")
    assistant.clock_value[0] = 60
    say(assistant, "confirme")
    assert system.calls == []


def test_status_and_media(viky):
    assistant, speaker, system = viky
    say(assistant, "état du pc")
    assert speaker.said[-1] == "Batterie à 82 %, en charge. Processeur à 12 %, mémoire utilisée à 45 %."
    say(assistant, "chanson suivante")
    say(assistant, "mets la luminosité à cinquante")
    assert system.calls == [("media", "next"), ("brightness", None, 50)]


def test_memory_flow(viky):
    assistant, speaker, _ = viky
    say(assistant, "appelle-moi guillaume")
    say(assistant, "souviens-toi que j'adore les tours de cartes")
    say(assistant, "bonjour")
    assert speaker.said == ["Enchantée, Guillaume. Je m'en souviendrai.", "C'est noté, je m'en souviendrai.",
                            "Bonjour Guillaume !"]
    assert assistant.brain.context("fr").endswith("j adore les tours de cartes.") or \
        "tours de cartes" in assistant.brain.context("fr")


def test_reminder_flow(viky):
    assistant, speaker, system = viky
    say(assistant, "rappelle-moi dans 10 minutes de sortir le gâteau")
    assert speaker.said[-1].startswith("C'est noté, je vous rappellerai aujourd'hui à")
    assert speaker.said[-1].endswith(": sortir le gâteau.")
    reminder = assistant.reminders.items[0]
    assistant._on_reminder(reminder)
    assert speaker.said[-1] == "Rappel : sortir le gâteau."
    assert "beep" in system.calls
    say(assistant, "minuteur de une heure et demie")
    assert speaker.said[-1] == "Minuteur de 1 heure et 30 minutes lancé."
    say(assistant, "rappelle-moi d'acheter du pain")
    assert speaker.said[-1].startswith("Pour quand ?")


@pytest.mark.parametrize("text, name", [
    ("Mode Jarvis", "ui_hud"), ("Affiche l'interface", "ui_hud"), ("Mode discret", "ui_widget"),
])
def test_interface_intents(text, name):
    assert parse(text, "fr").name == name


def test_interface_events(viky):
    assistant, speaker, _ = viky
    events = []
    assistant.listeners.append(lambda event, value: events.append((event, value)))
    say(assistant, "mode jarvis")
    say(assistant, "mode spectacle")
    assert ("heard", "mode jarvis") in events
    assert ("show_hud", None) in events
    assert ("stage", True) in events
    assert ("reply", "Mode spectacle activé. Que la magie commence.") in events


def test_hud_data(viky):
    assistant, _, _ = viky
    assistant.reminders.add(4102444800, "appeler Paul")  # en 2100
    info = assistant.hud_data(slow=False)
    assert info["reminders"] == ["le 1/1 à 0 h — appeler Paul"]
    assert info["status"]["battery"] == 82
