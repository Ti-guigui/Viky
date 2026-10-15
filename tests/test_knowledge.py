import types
from pathlib import Path

import pytest

from viky import brain as brain_module
from viky.assistant import Assistant
from viky.brain import REPORT_MARKER, Brain
from viky.config import Config
from viky.intents import parse
from viky.news import Headline, parse_feed
from viky.report import markdown_to_html, save_report
from viky.weather import Place, describe, parse_request


@pytest.mark.parametrize("text, name, args", [
    ("Quel temps fait-il ?", "weather", {"text": "quel temps fait il"}),
    ("Quelle est la météo à Lyon demain ?", "weather", {"text": "quelle est la météo à lyon demain"}),
    ("Est-ce qu'il va pleuvoir ?", "weather", {"text": "est ce qu il va pleuvoir"}),
    ("Donne-moi les grands titres", "news", {}),
    ("Quelles sont les infos ?", "news", {}),
    ("Approfondis le numéro deux", "news_detail", {"n": "deux"}),
    ("Raconte-moi la trois", "news_detail", {"n": "trois"}),
    ("Explique-moi l'article numéro 4", "news_detail", {"n": "4"}),
    ("Fais-moi une recherche complète sur les trous noirs", "research", {"query": "les trous noirs"}),
    ("Renseigne-toi sur l'histoire de la magie", "research", {"query": "l histoire de la magie"}),
    ("Approfondis", "followup", {}),
    ("Pourquoi le ciel est bleu ?", "ask", {"question": "pourquoi le ciel est bleu"}),
    ("C'est quoi un trou noir ?", "ask", {"question": "c est quoi un trou noir"}),
    ("Qui était Houdini ?", "ask", {"question": "qui était houdini"}),
    ("Affiche le rapport", "show_report", {}),
    ("Projette le rapport sur le projecteur", "show_report", {"projector": "sur le projecteur"}),
])
def test_french_intents(text, name, args):
    intent = parse(text, "fr")
    assert intent is not None, text
    assert (intent.name, intent.args) == (name, args)


def test_specific_questions_keep_their_intent():
    assert parse("Quelle heure est-il ?", "fr").name == "time"
    assert parse("Qu'est-ce que tu sais faire ?", "fr").name == "help"
    assert parse("Qui es-tu ?", "fr").name == "whoami"
    assert parse("What time is it?", "en").name == "time"


@pytest.mark.parametrize("text, name", [
    ("What's the weather like in London tomorrow?", "weather"), ("Read me the headlines", "news"),
    ("Tell me more about number two", "news_detail"), ("Research the history of magic", "research"),
    ("Why is the sky blue?", "ask"), ("Tell me more", "followup"),
])
def test_english_intents(text, name):
    assert parse(text, "en").name == name


@pytest.mark.parametrize("text, lang, city, day", [
    ("quel temps fait il", "fr", None, 0),
    ("quelle est la meteo a lyon demain", "fr", "lyon", 1),
    ("meteo a saint etienne", "fr", "saint etienne", 0),
    ("la meteo de demain", "fr", None, 1),
    ("quel temps fera t il apres demain a nice", "fr", "nice", 2),
    ("what s the weather like in london tomorrow", "en", "london", 1),
])
def test_weather_request(text, lang, city, day):
    assert parse_request(text, lang) == (city, day)


FORECAST = {
    "current": {"temperature_2m": 14.2, "apparent_temperature": 11.6, "weather_code": 3},
    "daily": {"weather_code": [3, 61, 0], "temperature_2m_min": [8.6, 7.1, 5],
              "temperature_2m_max": [16.4, 13, 18], "precipitation_probability_max": [10, 80, 0]},
}


def test_weather_sentences():
    paris = Place("Paris", 48.85, 2.35)
    assert describe(paris, FORECAST, 0, "fr") == (
        "À Paris, il fait 14 degrés, ressenti 12, ciel couvert. "
        "Aujourd'hui, entre 9 et 16 degrés. 10 % de risque de pluie.")
    assert describe(paris, FORECAST, 1, "fr") == (
        "Demain à Paris : pluie faible, entre 7 et 13 degrés. 80 % de risque de pluie.")
    assert describe(paris, FORECAST, 1, "en").startswith("Tomorrow in Paris: light rain")


RSS = b"""<?xml version="1.0" encoding="UTF-8"?><rss><channel>
<item><title>Premier titre</title><description>&lt;p&gt;Le r&#233;sum&#233;&lt;/p&gt;</description>
<link>https://exemple.fr/1</link></item>
<item><title>Deuxi&#232;me titre</title><description>Autre</description><link>https://exemple.fr/2</link></item>
</channel></rss>"""


def test_parse_feed():
    headlines = parse_feed(RSS)
    assert headlines[0] == Headline("Premier titre", "Le résumé", "https://exemple.fr/1")
    assert headlines[1].title == "Deuxième titre"


def test_report(tmp_path):
    html = markdown_to_html("## Origines\n- **Houdini** est né en 1874\n\nSource : https://fr.wikipedia.org")
    assert "<h3>Origines</h3>" in html
    assert "<li><strong>Houdini</strong> est né en 1874</li>" in html
    assert '<a href="https://fr.wikipedia.org">' in html
    path = save_report("l'histoire de la magie", "# Titre\nTexte", tmp_path)
    assert path.suffix == ".html" and "histoire-de-la-magie" in path.name
    assert "Texte" in path.read_text(encoding="utf-8")


# ------------------------------------------------------------ cerveau

def test_brain_prefers_local(monkeypatch):
    brain = Brain(claude_key="cle")
    monkeypatch.setattr(brain, "local_available", lambda: True)
    monkeypatch.setattr(brain, "_ollama", lambda messages, lang: "réponse locale")
    monkeypatch.setattr(brain, "_claude", lambda *a, **k: "réponse claude")
    assert brain.ask("pourquoi le ciel est bleu", "fr") == "réponse locale"
    assert brain.ask("actualité", "fr", deep=True) == "réponse claude"
    assert len(brain.history) == 4


def test_brain_falls_back_to_claude(monkeypatch):
    brain = Brain(claude_key="cle")
    monkeypatch.setattr(brain, "local_available", lambda: False)
    calls = []
    monkeypatch.setattr(brain, "_claude", lambda m, lang, web, effort: calls.append((web, effort)) or "ok")
    assert brain.ask("question", "fr") == "ok"
    assert calls == [(False, "low")]


def test_brain_without_anything(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    brain = Brain()
    monkeypatch.setattr(brain, "local_available", lambda: False)
    assert not brain.available
    with pytest.raises(brain_module.BrainUnavailable):
        brain.ask("question", "fr")


def test_research_splits_report(monkeypatch):
    brain = Brain(claude_key="cle")
    monkeypatch.setattr(brain, "_claude", lambda *a, **k: f"Résumé oral.\n{REPORT_MARKER}\n# Rapport\nDétails")
    assert brain.research("la magie", "fr") == ("Résumé oral.", "# Rapport\nDétails")


class FakeClient:
    """Imite le client Anthropic : une pause, puis la réponse finale."""

    def __init__(self):
        self.requests = []
        self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(create=self.create))

    def create(self, **request):
        self.requests.append(request)
        block = types.SimpleNamespace(type="text", text="Voici la réponse.")
        stop = "pause_turn" if len(self.requests) == 1 else "end_turn"
        return types.SimpleNamespace(stop_reason=stop, content=[block])


def test_claude_request_shape():
    brain = Brain(claude_key="cle")
    brain._client = FakeClient()
    assert brain._claude([{"role": "user", "content": "q"}], "fr", web=True, effort="high") == "Voici la réponse."
    first, second = brain._client.requests
    assert first["model"] == "claude-opus-5-5"
    assert first["tools"][0]["type"] == "web_search_20260209"
    assert first["fallbacks"] == "default"
    assert second["messages"][-1]["role"] == "assistant"  # reprise après pause


# ------------------------------------------------------------ assistant

class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text, lang):
        self.said.append(text)


def make_viky(brain, **kwargs):
    speaker = FakeSpeaker()
    projector = types.SimpleNamespace(NotAvailable=type("NotAvailable", (Exception,), {}))
    viky = Assistant(Config(), speaker, types.SimpleNamespace(), projector,
                     files=types.SimpleNamespace(), brain=brain, **kwargs)
    return viky, speaker


class FakeBrain:
    available = True
    use_claude = True

    def __init__(self):
        self.history = []
        self.asked = []

    def ask(self, question, lang, deep=False):
        self.asked.append(question)
        self.history.append(question)
        return f"Réponse à {question}"

    def follow_up(self, lang):
        return "Plus de détails."

    def explain_article(self, title, text, lang):
        return f"Explication de {title} ({text})"

    def research(self, topic, lang):
        return "Résumé.", "# Rapport"


def test_unknown_sentence_goes_to_brain():
    brain = FakeBrain()
    viky, speaker = make_viky(brain)
    viky.on_utterance({"fr": "viky la tour eiffel mesure combien"})
    assert brain.asked == ["la tour eiffel mesure combien"]
    assert speaker.said[-1] == "Réponse à la tour eiffel mesure combien"


def test_news_flow():
    news = types.SimpleNamespace(
        fetch_headlines=lambda feeds, count: [Headline("Titre A", "a", "l1"), Headline("Titre B", "b", "l2")],
        fetch_article=lambda h: f"texte de {h.title}")
    viky, speaker = make_viky(FakeBrain(), news=news)
    viky.on_utterance({"fr": "les infos"}, require_wake=False)
    assert speaker.said[1:3] == ["1. Titre A", "2. Titre B"]
    viky.on_utterance({"fr": "approfondis le numéro deux"}, require_wake=False)
    assert speaker.said[-1] == "Explication de Titre B (texte de Titre B)"
    viky.on_utterance({"fr": "raconte moi le cinq"}, require_wake=False)
    assert speaker.said[-1] == "Je n'ai que 2 titres. Choisissez un numéro entre 1 et 2."


def test_research_saves_report(monkeypatch, tmp_path):
    import viky.assistant as assistant_module

    saved = []
    monkeypatch.setattr(assistant_module, "save_report",
                        lambda topic, report: saved.append((topic, report)) or tmp_path / "r.html")
    viky, speaker = make_viky(FakeBrain())
    viky.on_utterance({"fr": "fais une recherche sur les illusionnistes"}, require_wake=False)
    assert saved == [("les illusionnistes", "# Rapport")]
    assert speaker.said[0].startswith("Je lance une recherche complète sur les illusionnistes")
    assert speaker.said[1] == "Résumé."
    assert viky.last_report == tmp_path / "r.html"


def test_weather_flow():
    weather = types.SimpleNamespace(report=lambda text, lang: f"Météo pour « {text} ».")
    viky, speaker = make_viky(FakeBrain(), weather=weather)
    viky.on_utterance({"fr": "quel temps fait-il à Lyon ?"}, require_wake=False)
    assert speaker.said == ["Météo pour « quel temps fait il à lyon »."]


def test_internet_down_is_explained():
    def broken(text, lang):
        raise OSError("réseau")

    viky, speaker = make_viky(FakeBrain(), weather=types.SimpleNamespace(report=broken))
    viky.on_utterance({"fr": "la météo"}, require_wake=False)
    assert speaker.said == ["Je n'arrive pas à joindre internet pour le moment."]


def test_time_sentences():
    from datetime import datetime

    from viky.messages import time_sentence

    assert time_sentence("fr", datetime(2026, 1, 1, 0, 9)) == "Il est minuit 9."
    assert time_sentence("fr", datetime(2026, 1, 1, 12, 0)) == "Il est midi."
    assert time_sentence("fr", datetime(2026, 1, 1, 1, 30)) == "Il est une heure 30."
    assert time_sentence("fr", datetime(2026, 1, 1, 21, 5)) == "Il est 21 heures 5."
