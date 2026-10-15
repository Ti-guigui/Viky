import json
import types
import urllib.error
import urllib.request

import pytest

from viky.assistant import Assistant
from viky.config import Config
from viky.intents import parse
from viky.magic import Card, Code, MagicShow, load_magic, parse_card
from viky.remote import Remote


@pytest.mark.parametrize("text, card", [
    ("sept de cœur", Card("7", "♥")), ("l'as de pique", Card("A", "♠")),
    ("la dame de carreau", Card("D", "♦")), ("roi de trèfle", Card("R", "♣")),
    ("10 de coeur", Card("10", "♥")), ("Queen of spades", Card("D", "♠")),
    ("7♥", Card("7", "♥")), ("V♣", Card("V", "♣")),
])
def test_parse_card(text, card):
    assert parse_card(text) == card


def test_not_a_card():
    assert parse_card("Paris") is None
    assert parse_card("sept de rien") is None


def test_card_names():
    assert Card("7", "♥").spoken("fr") == "le sept de cœur"
    assert Card("A", "♠").spoken("fr") == "l'as de pique"
    assert Card("D", "♦").spoken("en") == "the queen of diamonds"
    assert Card("D", "♦").label("en") == "Q"


def test_load_magic():
    show = load_magic({"codes": [{"phrase": "Regardez bien l'écran", "effet": "reveler"}],
                       "repliques": {"Es-tu prête ?": "Toujours."}})
    assert show.codes == [Code("regardez bien l ecran", "reveler", "")]
    assert show.find_code("Mesdames et messieurs, regardez bien l'écran maintenant").effect == "reveler"
    assert show.find_code("regardez bien") is None
    assert show.find_reply("Viky, es-tu prête ?") == "Toujours."


@pytest.mark.parametrize("text, name", [
    ("Mode spectacle", "stage_on"), ("Fin du spectacle", "stage_off"), ("Révèle la carte", "reveal"),
    ("Devine la carte", "guess"), ("Quelle est sa carte ?", "guess"), ("À quoi il pense ?", "guess"),
    ("Écris bienvenue sur l'écran", "show_text"), ("Efface l'écran", "clear_stage"),
])
def test_magic_intents(text, name):
    assert parse(text, "fr").name == name


class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text, lang):
        self.said.append(text)


class FakeStage:
    def __init__(self):
        self.shown = []

    def black(self):
        self.shown.append("noir")

    def show_text(self, text, style="fondu"):
        self.shown.append(("texte", text))

    def show_card(self, card, lang="fr"):
        self.shown.append(("carte", card))

    def hide(self):
        self.shown.append("cache")


def make_viky(**magic):
    config = Config()
    config.magic = MagicShow(**magic)
    speaker, stage = FakeSpeaker(), FakeStage()
    projector = types.SimpleNamespace(NotAvailable=RuntimeError, projector=lambda: None,
                                      slideshow_running=lambda: False)
    brain = types.SimpleNamespace(available=False, use_claude=False, history=[], persona=None)
    viky = Assistant(config, speaker, types.SimpleNamespace(), projector, files=types.SimpleNamespace(),
                     brain=brain, stage=stage, pause=lambda s: None)
    return viky, speaker, stage


def test_code_word_is_silent_and_needs_no_wake_word():
    viky, speaker, stage = make_viky(codes=[Code("regardez bien l ecran", "reveler")],
                                     secret="sept de coeur", stage_mode=True)
    viky.on_utterance({"fr": "et maintenant regardez bien l'écran", "en": "and now"})
    assert stage.shown == [("carte", Card("7", "♥"))]
    assert speaker.said == []


def test_code_words_only_in_stage_mode():
    viky, speaker, stage = make_viky(codes=[Code("faisons le noir", "noir")])
    viky.on_utterance({"fr": "faisons le noir"})
    assert stage.shown == []


def test_prepared_reply():
    viky, speaker, _ = make_viky(replies={"es tu prete": "Toujours."}, stage_mode=True)
    viky.on_utterance({"fr": "viky es-tu prête"})
    assert speaker.said == ["Toujours."]


def test_guess_routine():
    viky, speaker, stage = make_viky(secret="la dame de carreau")
    viky.on_utterance({"fr": "viky devine la carte"})
    assert speaker.said == ["Je me concentre…", "Je perçois une image… elle devient plus nette…",
                            "Je vois… la dame de carreau !"]
    assert stage.shown == [("carte", Card("D", "♦"))]


def test_guess_without_secret_recovers_gracefully():
    viky, speaker, stage = make_viky()
    viky.on_utterance({"fr": "viky devine la carte"})
    assert speaker.said == ["Mes visions sont troubles ce soir… Concentrez-vous plus fort."]
    assert stage.shown == []


def test_text_secret_and_stage_text():
    viky, _, stage = make_viky(secret="Paris")
    viky.on_utterance({"fr": "révèle la prédiction"}, require_wake=False)
    viky.on_utterance({"fr": "écris bienvenue sur l'écran"}, require_wake=False)
    viky.on_utterance({"fr": "écran noir"}, require_wake=False)
    viky.on_utterance({"fr": "efface l'écran"}, require_wake=False)
    assert stage.shown == [("texte", "Paris"), ("texte", "Bienvenue"), "noir", "cache"]


def test_stage_mode_is_quiet_and_sets_persona():
    viky, speaker, _ = make_viky()
    viky.on_utterance({"fr": "mode spectacle"}, require_wake=False)
    assert viky.magic.stage_mode and viky.brain.persona is not None
    speaker.said.clear()
    viky.on_utterance({"fr": "viky le chat dort"})
    assert speaker.said == []  # pas de « je n'ai pas compris » devant le public


def test_remote_over_http():
    viky, speaker, stage = make_viky()
    remote = Remote(viky.remote_action, "1234", port=0)
    remote.start()
    port = remote.server.server_address[1]

    def call(action, value="", pin="1234"):
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api", method="POST",
            data=json.dumps({"pin": pin, "action": action, "value": value}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read())

    try:
        page = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5).read().decode()
        assert "<title>Notes</title>" in page  # titre discret si quelqu'un voit l'écran
        with pytest.raises(urllib.error.HTTPError) as refused:
            call("etat", pin="0000")
        assert refused.value.code == 403
        assert call("secret", "7♥") == {"secret": "le sept de cœur", "spectacle": False,
                                         "message": "chargé : le sept de cœur"}
        assert call("reveler")["message"] == "révélé"
        assert stage.shown == [("carte", Card("7", "♥"))]
        call("dire", "Bonsoir")
        assert speaker.said == ["Bonsoir"]
        assert call("mode")["spectacle"] is True
    finally:
        remote.stop()
