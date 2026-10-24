"""Analisis envelope audio → parameter mulut karakter.

Tidak mengimpor Qt: bisa diuji tanpa GUI. Dipakai di M1 untuk animasi manual
dan di M3 untuk audio Gemini yang sebenarnya.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

SILENCE_LEVEL = 0.06


@dataclass(frozen=True)
class FrameFeatures:
    rms: float
    level: float
    centroid_hz: float
    shape: str


def classify(level: float, centroid_hz: float) -> str:
    """Petakan level + centroid ke salah satu tekstur mulut."""
    if level < SILENCE_LEVEL:
        return "M"
    if centroid_hz < 620:
        return "O"
    if centroid_hz < 1300:
        return "A"
    if centroid_hz < 2400:
        return "E"
    return "F"


class EnvelopeAnalyzer:
    """PCM int16 mono → RMS, level ternormalisasi, dan spectral centroid."""

    def __init__(self, sample_rate: int = 24_000, gain: float = 5.5) -> None:
        self.sample_rate = sample_rate
        self.gain = gain

    def feed(self, pcm: bytes) -> FrameFeatures:
        if not pcm:
            return FrameFeatures(0.0, 0.0, 0.0, "M")

        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        if samples.size == 0:
            return FrameFeatures(0.0, 0.0, 0.0, "M")

        rms = float(np.sqrt(np.mean(samples**2)))
        level = min(1.0, rms * self.gain)

        window = samples[-512:]
        if window.size < 512:
            window = np.pad(window, (0, 512 - window.size))
        window = window * np.hanning(window.size)
        spectrum = np.abs(np.fft.rfft(window))
        freqs = np.fft.rfftfreq(window.size, d=1.0 / self.sample_rate)
        total = float(spectrum.sum())
        centroid = float((freqs * spectrum).sum() / total) if total > 1e-9 else 0.0

        return FrameFeatures(rms, level, centroid, classify(level, centroid))


class VisemeDriver:
    """Smoothing attack/release supaya mulut tidak berkedip-kedip."""

    def __init__(self, attack: float = 0.04, release: float = 0.09) -> None:
        self.attack = attack
        self.release = release
        self.level = 0.0
        self.shape = "M"

    def reset(self) -> None:
        self.level = 0.0
        self.shape = "M"

    def update(self, target_level: float, shape: str, dt: float) -> tuple[str, float]:
        target = max(0.0, min(1.0, target_level))
        tau = self.attack if target > self.level else self.release
        if tau <= 0:
            self.level = target
        else:
            alpha = 1.0 - math.exp(-max(0.0, dt) / tau)
            self.level += (target - self.level) * alpha

        if target < SILENCE_LEVEL and self.level < 0.02:
            self.shape = "M"
            self.level = 0.0
        elif target >= SILENCE_LEVEL:
            self.shape = shape

        return self.shape, self.level
