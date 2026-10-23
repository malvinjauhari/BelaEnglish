"""Pemuatan dan penyimpanan konfigurasi.

Urutan prioritas:
1. ``GEMINI_API_KEY`` dari environment.
2. ``config.json`` di root project.
3. Default di ``config.example.json``.

Tidak pernah menulis API key ke log atau repo.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
EXAMPLE_PATH = PROJECT_ROOT / "config.example.json"

DEFAULTS: dict[str, Any] = {
    "gemini_api_key": "",
    "model": "models/gemini-2.5-flash-native-audio-preview-12-2025",
    "model_fallbacks": [
        "models/gemini-2.5-flash-native-audio-preview-12-2025",
        "models/gemini-live-2.5-flash-preview",
    ],
    "voice": "Kore",
    "audio": {
        "input_device": None,
        "output_device": None,
        "half_duplex": False,
        "silence_ms": 650,
        "prefix_padding_ms": 300,
    },
    "persona": {
        "character_name": "Rey",
        "user_name": "",
        "cefr_level": "B1",
        "spice_level": 1,
        "correction_level": 2,
        "indonesian_help": True,
        "auto_emotion": True,
    },
    "ui": {
        "always_on_top": False,
        "theme": "midnight",
        "fps_cap": 60,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Gabungkan dua dict secara rekursif tanpa memodifikasi input."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    """Konfigurasi aplikasi berbasis JSON dengan default bertingkat."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else CONFIG_PATH
        self.data: dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.load()

    # ── baca / tulis ──────────────────────────────────────────────────────
    def load(self) -> None:
        raw: dict[str, Any] = {}
        if EXAMPLE_PATH.exists():
            try:
                raw = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raw = {}
        merged = _deep_merge(DEFAULTS, raw)

        if self.path.exists():
            try:
                user = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(user, dict):
                    merged = _deep_merge(merged, user)
            except (OSError, json.JSONDecodeError):
                pass

        self.data = merged

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    # ── akses ─────────────────────────────────────────────────────────────
    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def set(self, value: Any, *keys: str) -> None:
        if not keys:
            raise ValueError("minimal satu key dibutuhkan")
        node = self.data
        for key in keys[:-1]:
            child = node.get(key)
            if not isinstance(child, dict):
                child = {}
                node[key] = child
            node = child
        node[keys[-1]] = value

    @property
    def api_key(self) -> str:
        return os.environ.get("GEMINI_API_KEY") or self.get(
            "gemini_api_key", default=""
        )

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key.strip())
