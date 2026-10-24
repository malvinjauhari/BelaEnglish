"""Komponen kontrol: tombol mic, pemilih mode, dan statistik sesi."""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

MODES: list[tuple[str, str]] = [
    ("free_talk", "Free Talk"),
    ("roleplay", "Roleplay"),
    ("drill", "Drill"),
    ("review", "Review"),
]


class MicOrb(QWidget):
    """Tombol mic bulat: klik untuk mulai/akhiri sesi, muting lewat hotkey."""

    muted_changed = pyqtSignal(bool)
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(72, 72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Mulai sesi")
        self._connected = False
        self._muted = False
        self._level = 0.0
        self._phase = 0.0
        self._pulse = QTimer(self)
        self._pulse.setInterval(33)
        self._pulse.timeout.connect(self._tick)
        self._pulse.start()

    @property
    def muted(self) -> bool:
        return self._muted

    @property
    def connected(self) -> bool:
        return self._connected

    def set_connected(self, connected: bool) -> None:
        if connected == self._connected:
            return
        self._connected = connected
        if not connected:
            self.set_muted(False)
        self.update()

    def set_muted(self, muted: bool) -> None:
        if muted == self._muted:
            return
        self._muted = muted
        self.update()

    def toggle_muted(self) -> None:
        self.set_muted(not self._muted)
        self.muted_changed.emit(self._muted)

    def set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, level))

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(72, 72)

    def _tick(self) -> None:
        self._phase += 0.033
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        cx, cy = self.width() / 2.0, self.height() / 2.0
        base_r = 24.0
        if self._muted:
            accent = QColor("#FF6B6B")
        elif self._connected:
            accent = QColor("#7C5CFF")
        else:
            accent = QColor("#6C7796")

        if self._connected:
            pulse = (math.sin(self._phase * 2.4) + 1.0) / 2.0
            halo_r = base_r + 7.0 + pulse * 3.0 + self._level * 10.0
            halo = QRadialGradient(QPointF(cx, cy), halo_r)
            halo.setColorAt(0.55, QColor(accent.red(), accent.green(), accent.blue(), 46))
            halo.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            p.drawEllipse(QPointF(cx, cy), halo_r, halo_r)

        body = QRadialGradient(QPointF(cx, cy - 6), base_r * 1.5)
        body.setColorAt(0.0, QColor("#2A3457"))
        body.setColorAt(1.0, QColor("#161D34"))
        p.setBrush(body)
        p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 170), 1.4))
        p.drawEllipse(QPointF(cx, cy), base_r, base_r)

        icon = QColor("#E8ECF8") if self._connected else QColor("#98A2C0")
        pen = QPen(icon, 2.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        capsule = QPainterPath()
        capsule.addRoundedRect(QRectF(cx - 5.0, cy - 13.0, 10.0, 16.0), 5.0, 5.0)
        p.drawPath(capsule)
        arc = QPainterPath()
        arc.moveTo(cx - 9.0, cy - 2.0)
        arc.cubicTo(cx - 9.0, cy + 9.0, cx + 9.0, cy + 9.0, cx + 9.0, cy - 2.0)
        p.drawPath(arc)
        p.drawLine(QPointF(cx, cy + 9.0), QPointF(cx, cy + 14.0))

        if self._muted:
            p.setPen(QPen(QColor("#FF6B6B"), 2.8))
            p.drawLine(QPointF(cx - 12.0, cy + 12.0), QPointF(cx + 12.0, cy - 12.0))


class StatChip(QWidget):
    def __init__(self, name: str, value: str = "0", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        self._value = QLabel(value)
        self._value.setObjectName("StatValue")
        self._name = QLabel(name)
        self._name.setObjectName("StatName")
        layout.addWidget(self._value)
        layout.addWidget(self._name)

    def set_value(self, value: str | int) -> None:
        self._value.setText(str(value))


class ControlBar(QWidget):
    """Baris kontrol horizontal di atas transkrip."""

    mode_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ControlBar")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for key, label in MODES:
            button = QPushButton(label)
            button.setObjectName("ModeChip")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumWidth(78)
            button.clicked.connect(lambda _checked=False, k=key: self._on_mode(k))
            self._group.addButton(button)
            self._buttons[key] = button
            root.addWidget(button)
        self._buttons["free_talk"].setChecked(True)

        root.addStretch(1)

        self.stat_wpm = StatChip("WPM", "—")
        self.stat_words = StatChip("KATA BARU", "0")
        self.stat_fixes = StatChip("KOREKSI", "0")
        for chip in (self.stat_wpm, self.stat_words, self.stat_fixes):
            root.addSpacing(6)
            root.addWidget(chip)

    def set_mode(self, mode: str) -> None:
        button = self._buttons.get(mode)
        if button is not None and not button.isChecked():
            button.setChecked(True)

    def set_stats(self, wpm: int | None, new_words: int, fixes: int) -> None:
        self.stat_wpm.set_value("—" if not wpm else wpm)
        self.stat_words.set_value(new_words)
        self.stat_fixes.set_value(fixes)

    def _on_mode(self, key: str) -> None:
        self.mode_changed.emit(key)
