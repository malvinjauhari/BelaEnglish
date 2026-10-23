"""Event bus tipis di atas pyqtSignal.

Satu-satunya modul di ``core/`` yang boleh mengimpor PyQt6. Semua komunikasi
dari pipeline async (M2) ke UI lewat sini.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class EventBus(QObject):
    # state & mode
    state_changed = pyqtSignal(str)      # AppState.value
    mode_changed = pyqtSignal(str)       # Mode.value
    status_changed = pyqtSignal(str)     # teks human-readable

    # percakapan
    message_added = pyqtSignal(str, str)     # speaker, text
    correction_added = pyqtSignal(str, str, str)  # user_text, better, note
    emotion_changed = pyqtSignal(str)

    # audio
    level_changed = pyqtSignal(float)     # 0.0 - 1.0
    muted_changed = pyqtSignal(bool)

    # diagnostik
    error_occurred = pyqtSignal(str)
    latency_reported = pyqtSignal(int)    # ms
