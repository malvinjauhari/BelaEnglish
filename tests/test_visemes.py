import numpy as np

from app.core.visemes import (
    SILENCE_LEVEL,
    EnvelopeAnalyzer,
    VisemeDriver,
    classify,
)

SR = 24_000


def tone(freq: float, amplitude: float = 0.5, frames: int = 1024) -> bytes:
    t = np.arange(frames) / SR
    samples = np.sin(2 * np.pi * freq * t) * amplitude * 32767
    return samples.astype(np.int16).tobytes()


def test_silence_is_closed_mouth():
    features = EnvelopeAnalyzer().feed(b"\x00\x00" * 1024)
    assert features.level == 0.0
    assert features.shape == "M"


def test_empty_input_is_safe():
    features = EnvelopeAnalyzer().feed(b"")
    assert features.level == 0.0
    assert features.shape == "M"


def test_low_frequency_opens_round_mouth():
    features = EnvelopeAnalyzer().feed(tone(200))
    assert features.level > 0.5
    assert features.shape == "O"


def test_mid_frequency_maps_to_a():
    features = EnvelopeAnalyzer().feed(tone(800))
    assert features.shape == "A"


def test_high_frequency_maps_to_e():
    features = EnvelopeAnalyzer().feed(tone(1800))
    assert features.shape == "E"


def test_classify_thresholds():
    assert classify(0.0, 1000) == "M"
    assert classify(0.5, 100) == "O"
    assert classify(0.5, 900) == "A"
    assert classify(0.5, 2000) == "E"
    assert classify(0.5, 5000) == "F"


def test_driver_attacks_and_releases():
    driver = VisemeDriver()
    shape, level = driver.update(1.0, "A", 0.016)
    assert shape == "A"
    assert 0.0 < level < 1.0

    for _ in range(20):
        shape, level = driver.update(1.0, "A", 0.016)
    assert level > 0.9

    previous = level
    for _ in range(3):
        _, level = driver.update(0.0, "M", 0.016)
    assert level < previous
    assert level > 0.0  # release belum selesai


def test_driver_returns_to_rest():
    driver = VisemeDriver()
    for _ in range(10):
        driver.update(1.0, "A", 0.02)
    for _ in range(200):
        shape, level = driver.update(0.0, "M", 0.02)
    assert (shape, level) == ("M", 0.0)


def test_custom_silence_threshold_constant():
    assert 0.0 < SILENCE_LEVEL < 0.1
