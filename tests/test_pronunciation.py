import types

import numpy as np
import pytest

from viky.assistant import Assistant
from viky.config import Config
from viky.intents import all_patterns, parse
from viky.memory import Memory
from viky.pronunciation import Pronunciation, command_vocabulary, sound_key
from viky.recognizer import WhisperRecognizer
from viky.reminders import Reminders

VOCABULARY = command_vocabulary(all_patterns())


@pytest.mark.parametrize("a, b", [
    ("rappelle", "wappelle"), ("rappelle", "appelle"), ("précédente", "pécédente"),
    ("carte", "cate"), ("diaporama", "diapoama"), ("révèle", "wévèle"),
])
def test_sound_key_ignores_r(a, b):
    assert sound_key(a) == sound_key(b)


def test_vocabulary_has_real_words_only():
    assert {"projette", "precedente", "rappelle", "meteo", "spectacle"} <= VOCABULARY
    assert "query" not in VOCABULARY


@pytest.mark.parametrize("heard, intent", [
    ("pwojette la pésentation mawiage", "project"),
    ("diapo pécédente", "previous"),
    ("wévèle la cate", "reveal"),
    ("lance le diapoama", "show_start"),
    ("enwegistre", "save"),
])
def test_sound_alike_rescues_commands(heard, intent):
    assert parse(heard, "fr") is None or parse(heard, "fr").name != intent
    fixed = Pronunciation(vocabulary=VOCABULARY).sound_alike(heard)
    assert parse(fixed, "fr").name == intent


def test_learn_and_correct(tmp_path):
    p = Pronunciation(tmp_path / "p.json", VOCABULARY)
    assert p.learn("Rappelle-moi d'appeler Paul", "Wappelle-moi d'appeler Paul") == [("wappelle", "rappelle")]
    assert p.learn("Reviens à la diapo précédente", "Viens à la diapo pas cédante") == [
        ("viens", "reviens"), ("pas cedante", "precedente")]
    p.learn("Écran noir", "Écran noir")  # rien à apprendre
    p.save()
    again = Pronunciation(tmp_path / "p.json", VOCABULARY)
    assert again.correct("Wappelle-moi de partir à 8h") == "rappelle moi de partir à 8h"
    assert again.correct("diapo pas cédante") == "diapo precedente"
    assert again.correct("Écran noir") == "écran noir"


def test_learning_ignores_small_words(tmp_path):
    p = Pronunciation(tmp_path / "p.json")
    assert p.learn("Mets la musique en pause", "Mets le musique en pause") == []


def test_set_name_vs_mispronounced_reminder():
    assert parse("Appelle-moi Guillaume", "fr").name == "set_name"
    assert parse("Appelle-moi d'appeler Paul à 18h", "fr").name == "remind"
    assert parse("Appelle-moi dans 10 minutes", "fr").name == "remind"


class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text, lang):
        self.said.append(text)


def make_viky(tmp_path, pronunciation):
    projector = types.SimpleNamespace(NotAvailable=RuntimeError, slideshow_running=lambda: True,
                                      calls=[], slide_previous=lambda: projector.calls.append("previous"))
    brain = types.SimpleNamespace(available=False, use_claude=False, history=[], persona=None, context=None)
    viky = Assistant(Config(), FakeSpeaker(), types.SimpleNamespace(), projector,
                     files=types.SimpleNamespace(), brain=brain, stage=types.SimpleNamespace(),
                     memory=Memory(tmp_path / "m.json"), reminders=Reminders(tmp_path / "r.json"),
                     pronunciation=pronunciation)
    return viky, projector


def test_assistant_uses_sound_alike(tmp_path):
    viky, projector = make_viky(tmp_path, Pronunciation(vocabulary=VOCABULARY))
    viky.on_utterance({"fr": "Viky, diapo pécédente"})
    assert projector.calls == ["previous"]


def test_assistant_uses_learned_wake_word(tmp_path):
    pronunciation = Pronunciation(tmp_path / "p.json", VOCABULARY)
    pronunciation.learn("Viky", "Biki")
    viky, projector = make_viky(tmp_path, pronunciation)
    viky.on_utterance({"fr": "Biki, diapo précédente"})
    assert projector.calls == ["previous"]


class FakeModel:
    """Imite faster-whisper : détecte l'anglais avec une probabilité donnée."""

    def __init__(self, lang, probability):
        self.lang, self.probability, self.calls = lang, probability, []

    def transcribe(self, samples, language=None, **kwargs):
        self.calls.append((language, kwargs["beam_size"]))
        text = "hello" if language in (None, "en") and self.lang == "en" else "bonjour"
        info = types.SimpleNamespace(language=language or self.lang, language_probability=self.probability)
        return [types.SimpleNamespace(text=text)], info


def make_recognizer(model, langs=("fr", "en")):
    recognizer = WhisperRecognizer.__new__(WhisperRecognizer)
    recognizer.langs, recognizer.other_lang_threshold, recognizer.beam_size = list(langs), 0.9, 5
    recognizer.prompts = {"fr": "Viky.", "en": "Viky."}
    recognizer.model = model
    return recognizer


def test_uncertain_english_is_retranscribed_in_french():
    model = FakeModel("en", 0.6)  # un accent fait hésiter Whisper
    assert make_recognizer(model).transcribe(np.zeros(1600, dtype=np.int16).tobytes()) == {"fr": "bonjour"}
    assert model.calls == [(None, 5), ("fr", 5)]


def test_confident_english_is_kept():
    model = FakeModel("en", 0.97)
    assert make_recognizer(model).transcribe(np.zeros(1600, dtype=np.int16).tobytes()) == {"en": "hello"}


def test_learned_corrections_do_not_alter_dictation(tmp_path):
    pronunciation = Pronunciation(tmp_path / "p.json", VOCABULARY)
    pronunciation.learn("Mets la musique en pause", "Mais la musique en pause")  # apprend mais -> mets
    pronunciation.learn("Révèle la carte", "Wevelacate")
    viky, projector = make_viky(tmp_path, pronunciation)
    answers = []
    viky.ask("fr", "ok", lambda lang, text: answers.append(text))
    viky.on_utterance({"fr": "Je viendrai, mais en retard"})
    assert answers == ["je viendrai, mais en retard".replace(",", "")]  # « mais » intact dans la dictée
    shown = []
    viky.stage = types.SimpleNamespace(show_text=lambda t, s="": shown.append(t))
    viky.magic.secret = "Paris"
    viky.on_utterance({"fr": "Viky Wevelacate"})
    assert shown == ["Paris"]
