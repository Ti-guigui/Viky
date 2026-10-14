"""Traitement du son du micro : découpage des phrases et détection du double clap."""

from __future__ import annotations

from collections import deque

import numpy as np

SAMPLE_RATE = 16000
BLOCK_SECONDS = 0.1
BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_SECONDS)


def rms(samples: np.ndarray) -> float:
    return float(np.sqrt(np.mean(samples.astype(np.float32) ** 2))) if samples.size else 0.0


class Segmenter:
    """Découpe le flux du micro en phrases, en repérant les silences."""

    def __init__(self, silence_blocks: int = 8, max_blocks: int = 100,
                 min_speech_blocks: int = 3, preroll_blocks: int = 3,
                 min_level: float = 300.0) -> None:
        self.silence_blocks = silence_blocks
        self.max_blocks = max_blocks
        self.min_speech_blocks = min_speech_blocks
        self.min_level = min_level
        self.preroll: deque[bytes] = deque(maxlen=preroll_blocks)
        self.floor: float | None = None
        self.reset()

    def reset(self) -> None:
        self.active = False
        self.buffer: list[bytes] = []
        self.speech = 0
        self.silent = 0
        self.preroll.clear()

    def feed(self, block: bytes, samples: np.ndarray) -> bytes | None:
        """Ajoute un bloc de son ; renvoie une phrase complète quand elle se termine."""
        level = rms(samples)
        if self.floor is None:
            self.floor = level
        loud = level > max(self.floor * 3.0, self.min_level)

        if not self.active:
            if loud:
                self.active = True
                self.buffer = [*self.preroll, block]
                self.speech, self.silent = 1, 0
            else:
                self.floor = 0.95 * self.floor + 0.05 * level
                self.preroll.append(block)
            return None

        self.buffer.append(block)
        if loud:
            self.speech += 1
            self.silent = 0
        else:
            self.silent += 1
        if self.silent >= self.silence_blocks or len(self.buffer) >= self.max_blocks:
            segment = b"".join(self.buffer) if self.speech >= self.min_speech_blocks else None
            self.reset()
            return segment
        return None


class ClapDetector:
    """Détecte deux claquements de mains rapprochés."""

    def __init__(self, sensitivity: float = 0.5, min_gap: float = 0.15, max_gap: float = 1.0) -> None:
        sensitivity = min(max(sensitivity, 0.0), 1.0)
        self.peak_threshold = 32768 * (0.9 - 0.6 * sensitivity)
        self.min_gap = min_gap
        self.max_gap = max_gap
        self.last_clap: float | None = None
        self.previous_level = 0.0

    def feed(self, samples: np.ndarray, now: float) -> bool:
        """Renvoie True au deuxième clap d'une paire."""
        level = rms(samples)
        peak = float(np.abs(samples.astype(np.int32)).max()) if samples.size else 0.0
        # Un clap est un pic très court et très fort qui surgit dans un relatif silence.
        is_clap = (peak >= self.peak_threshold
                   and peak >= 4 * max(level, 1.0)
                   and self.previous_level < peak * 0.1)
        self.previous_level = level
        if not is_clap:
            return False
        if self.last_clap is not None and self.min_gap <= now - self.last_clap <= self.max_gap:
            self.last_clap = None
            return True
        self.last_clap = now
        return False
