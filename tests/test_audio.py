import numpy as np

from viky.audio import BLOCK_SIZE, ClapDetector, Segmenter
from viky.text import strip_wake_word

rng = np.random.default_rng(0)


def silence():
    return (rng.normal(0, 50, BLOCK_SIZE)).astype(np.int16)


def speech():
    t = np.arange(BLOCK_SIZE) / 16000
    return (4000 * np.sin(2 * np.pi * 220 * t) + rng.normal(0, 50, BLOCK_SIZE)).astype(np.int16)


def clap():
    block = silence()
    block[500:540] = 30000
    return block


def feed(segmenter, blocks):
    out = [segmenter.feed(b.tobytes(), b) for b in blocks]
    return [s for s in out if s]


def test_segmenter_cuts_a_sentence():
    seg = Segmenter()
    segments = feed(seg, [silence()] * 10 + [speech()] * 10 + [silence()] * 10)
    assert len(segments) == 1
    assert len(segments[0]) == (3 + 10 + 8) * BLOCK_SIZE * 2


def test_segmenter_ignores_short_noises():
    seg = Segmenter()
    assert feed(seg, [silence()] * 10 + [speech()] + [silence()] * 10) == []


def test_double_clap():
    detector = ClapDetector()
    results = [detector.feed(b, i * 0.1) for i, b in enumerate(
        [silence(), clap(), silence(), silence(), clap(), silence()])]
    assert results == [False, False, False, False, True, False]


def test_single_clap_and_speech_do_not_wake():
    detector = ClapDetector()
    blocks = [clap()] + [silence()] * 20 + [clap()] + [speech()] * 10
    assert not any(detector.feed(b, i * 0.1) for i, b in enumerate(blocks))


def test_strip_wake_word():
    words = ["viky", "vicky"]
    assert strip_wake_word("dis vicky ouvre chrome", words) == (True, "ouvre chrome")
    assert strip_wake_word("ouvre chrome viky", words) == (True, "ouvre chrome")
    assert strip_wake_word("ouvre chrome", words) == (False, "ouvre chrome")


def test_wake_word_misheard():
    from viky.config import Config

    words = Config().wake_words
    assert strip_wake_word("mickey quelle heure est il", words) == (True, "quelle heure est il")
    assert strip_wake_word("vickie ouvre chrome", words) == (True, "ouvre chrome")
    assert strip_wake_word("ouvre la video", words) == (False, "ouvre la video")
