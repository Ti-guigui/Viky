import types
from pathlib import Path

import pytest

from viky.assistant import Assistant
from viky.config import Config
from viky.intents import parse


@pytest.mark.parametrize("text, name, args", [
    ("Projette la présentation mariage", "project", {"target": "la presentation mariage"}),
    ("Mets le PDF contrat sur le projecteur", "project", {"target": "le pdf contrat"}),
    ("Envoie ça sur le grand écran", "project_current", {}),
    ("Ouvre le tableau budget", "open_file", {"target": "le tableau budget"}),
    ("Diapo suivante", "next", {}),
    ("Suivant", "next", {}),
    ("Reviens en arrière", "previous", {}),
    ("Va à la diapo cinq", "goto", {"n": "cinq"}),
    ("Lance le diaporama", "show_start", {}),
    ("Arrête la présentation", "show_end", {}),
    ("Écran noir", "black", {}),
    ("Rallume l'écran", "resume", {}),
    ("Mets en plein écran", "fullscreen", {}),
    ("Duplique l'écran", "display_clone", {}),
    ("Mets 500 dans la cellule B3", "cell_set", {"value": "500", "cell": "b3"}),
    ("Écris payé dans la case C 12", "cell_set", {"value": "paye", "cell": "c 12"}),
    ("La cellule B trois vaut douze", "cell_set", {"cell": "b trois", "value": "douze"}),
    ("Lis la cellule A1", "cell_get", {"cell": "a1"}),
    ("Enregistre", "save", {}),
    ("Change le titre de la diapo en Bienvenue à tous", "slide_title", {"text": "bienvenue a tous"}),
    ("Ferme le fichier", "close_current", {}),
    ("Ouvre mes documents", "open", {"target": "mes documents"}),
])
def test_french_projection_intents(text, name, args):
    intent = parse(text, "fr")
    assert intent is not None, text
    assert (intent.name, intent.args) == (name, args)


@pytest.mark.parametrize("text, name", [
    ("Next slide", "next"), ("Go to slide three", "goto"), ("Start the slideshow", "show_start"),
    ("Put the budget spreadsheet on the projector", "project"), ("Put 12 in cell B2", "cell_set"),
    ("Black screen", "black"), ("Open the pdf contract", "open_file"),
])
def test_english_projection_intents(text, name):
    assert parse(text, "en").name == name


class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text, lang):
        self.said.append(text)


class FakeProjector:
    class NotAvailable(Exception):
        pass

    def __init__(self, screen=True, show=False):
        self.calls = []
        self.screen = screen
        self.show = show
        self.cells = {}

    def projector(self):
        return {"device": "DISPLAY2"} if self.screen else None

    def open_file(self, path, on_projector):
        self.calls.append(("open", path.name, on_projector))
        return True

    def slideshow_running(self):
        return self.show

    def slide_next(self):
        self.calls.append("slide_next")

    def slide_goto(self, n):
        self.calls.append(("goto", n))

    def press(self, *keys):
        self.calls.append(("press", keys))

    def excel_set(self, cell, value):
        self.cells[cell] = value

    def excel_get(self, cell):
        if not self.cells:
            raise self.NotAvailable
        return self.cells.get(cell)


class FakeFiles:
    def find(self, spoken):
        return Path("/x/Mariage Julie.pptx") if "mariage" in spoken else None


def make(projector):
    speaker = FakeSpeaker()
    actions = types.SimpleNamespace(clean_target=lambda t: t)
    brain = types.SimpleNamespace(available=False, use_claude=False, history=[])
    viky = Assistant(Config(), speaker, actions, projector, FakeFiles(), brain=brain)
    return viky, speaker


def run(viky, text):
    viky.on_utterance({"fr": text}, require_wake=False)


def test_project_file():
    proj = FakeProjector()
    viky, speaker = make(proj)
    run(viky, "projette la présentation mariage")
    assert proj.calls == [("open", "Mariage Julie.pptx", True)]
    assert speaker.said == ["J'affiche Mariage Julie sur le projecteur."]


def test_project_without_projector_opens_on_pc():
    proj = FakeProjector(screen=False)
    viky, speaker = make(proj)
    run(viky, "projette la présentation mariage")
    assert proj.calls == [("open", "Mariage Julie.pptx", False)]
    assert speaker.said[0].startswith("Je ne détecte pas de projecteur")


def test_file_not_found():
    viky, speaker = make(FakeProjector())
    run(viky, "projette le pdf contrat")
    assert speaker.said == ["Je n'ai pas trouvé de fichier qui ressemble à contrat."]


def test_next_uses_slideshow_or_keys():
    proj = FakeProjector(show=True)
    viky, speaker = make(proj)
    run(viky, "suivant")
    run(viky, "va à la diapo douze")
    assert proj.calls == ["slide_next", ("goto", 12)]
    assert speaker.said == []  # silencieux pendant le spectacle
    proj.show = False
    run(viky, "suivant")
    assert proj.calls[-1] == ("press", ("pagedown",))


def test_excel_by_voice():
    proj = FakeProjector()
    viky, speaker = make(proj)
    run(viky, "mets douze virgule cinq dans la cellule b trois")
    assert proj.cells == {"B3": 12.5}
    assert speaker.said[-1] == "C'est fait, B3 vaut 12,5."
    run(viky, "lis la cellule b3")
    assert speaker.said[-1] == "La cellule B3 contient 12,5."


def test_unavailable_is_explained():
    viky, speaker = make(FakeProjector())
    run(viky, "lis la cellule b3")
    assert speaker.said[-1].startswith("Ce n'est pas possible pour le moment")
