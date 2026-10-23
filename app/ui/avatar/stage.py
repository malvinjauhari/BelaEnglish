"""Widget panggung karakter: mengatur timer 60 fps dan input kursor."""

from __future__ import annotations

import time
from collections import deque

from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QSizePolicy, QWidget

from .rig import Rig


class AvatarStage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AvatarStage")
        self.setMinimumSize(320, 380)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.rig = Rig()
        self._interval_ms = 16
        self._last = time.perf_counter()
        self._frames: deque[float] = deque(maxlen=90)
        self._slow_for = 0.0
        self._fast_for = 0.0

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._timer.start(self._interval_ms)

    # ── API untuk lapisan lain ────────────────────────────────────────────
    def set_state(self, state: str) -> None:
        self.rig.set_state(state)

    def set_emotion(self, emotion: str) -> None:
        self.rig.set_emotion(emotion)

    def set_audio(self, shape: str, level: float) -> None:
        self.rig.set_audio(shape, level)

    def force_blink(self) -> None:
        self.rig.force_blink()

    # ── animasi ───────────────────────────────────────────────────────────
    def _tick(self) -> None:
        now = time.perf_counter()
        dt = now - self._last
        self._last = now

        self.rig.update(dt)
        self._adapt_fps(dt)
        self.update()

    def _adapt_fps(self, dt: float) -> None:
        """Turunkan ke 30 fps kalau mesin tidak kuat, naikkan lagi kalau lega."""
        if dt <= 0.0:
            return
        self._frames.append(dt)
        if len(self._frames) < 30:
            return

        average = sum(self._frames) / len(self._frames)
        if average > 0.024:
            self._slow_for += dt
            self._fast_for = 0.0
        elif average < 0.019:
            self._fast_for += dt
            self._slow_for = 0.0
        else:
            self._slow_for = 0.0
            self._fast_for = 0.0

        if self._slow_for > 3.0 and self._interval_ms < 33:
            self._interval_ms = 33
            self._timer.setInterval(self._interval_ms)
            self._slow_for = 0.0
            self._frames.clear()
        elif self._fast_for > 6.0 and self._interval_ms > 16:
            self._interval_ms = 16
            self._timer.setInterval(self._interval_ms)
            self._fast_for = 0.0
            self._frames.clear()

    # ── event Qt ──────────────────────────────────────────────────────────
    def paintEvent(self, _event) -> None:  # noqa: N802 (API Qt)
        painter = QPainter(self)
        self.rig.paint(painter, self.width(), self.height())

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        pos = event.position()
        dx = (pos.x() - center.x()) / max(1.0, self.width() / 2.0)
        dy = (pos.y() - center.y()) / max(1.0, self.height() / 2.0)
        self.rig.set_look(dx, dy)

    def leaveEvent(self, _event) -> None:  # noqa: N802
        self.rig.set_look(0.0, 0.0)

    def mousePressEvent(self, _event) -> None:  # noqa: N802
        # Rey bereaksi kecil saat diklik.
        self.rig.force_blink()
        self.rig.set_emotion("surprised")
        QTimer.singleShot(900, lambda: self.rig.set_emotion("neutral"))
