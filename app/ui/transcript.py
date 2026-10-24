"""Panel transkrip percakapan + kartu koreksi."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class _Bubble(QFrame):
    def __init__(self, speaker: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        rey = speaker.lower() == "rey"
        self.setObjectName("BubbleRey" if rey else "BubbleYou")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 9, 14, 11)
        layout.setSpacing(3)

        name = QLabel("REY" if rey else "KAMU")
        name.setObjectName("SpeakerName")
        layout.addWidget(name)

        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setMaximumWidth(520)
        layout.addWidget(body)
        self._body = body

    def set_text(self, text: str) -> None:
        self._body.setText(text)


class _CorrectionCard(QFrame):
    def __init__(self, original: str, better: str, note: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CorrectionCard")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 10)
        layout.setSpacing(4)

        title = QLabel("KOREKSI")
        title.setObjectName("SpeakerName")
        layout.addWidget(title)

        if original:
            before = QLabel(original)
            before.setWordWrap(True)
            before.setStyleSheet("color: #98A2C0; text-decoration: line-through;")
            before.setMaximumWidth(520)
            layout.addWidget(before)

        fix = QLabel(better)
        fix.setObjectName("CorrectionFix")
        fix.setWordWrap(True)
        fix.setMaximumWidth(520)
        layout.addWidget(fix)

        if note:
            hint = QLabel(note)
            hint.setObjectName("CorrectionNote")
            hint.setWordWrap(True)
            hint.setMaximumWidth(520)
            layout.addWidget(hint)


class TranscriptView(QScrollArea):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(2, 6, 10, 6)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)
        self.setWidget(self._container)

        self._empty = QLabel(
            "Tekan mic, lalu ngobrol santai dengan Rey.\n"
            "Belum ada yang perlu kamu siapkan — cukup bilang hi."
        )
        self._empty.setObjectName("EmptyHint")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._layout.insertWidget(0, self._empty)

        self._live_row: QHBoxLayout | None = None
        self._live_bubble: _Bubble | None = None
        self._live_speaker: str | None = None

    # ── API ───────────────────────────────────────────────────────────────
    def add_message(self, speaker: str, text: str) -> None:
        if not text.strip():
            return
        if self._live_speaker == speaker.lower():
            self._remove_live()
        self._empty.hide()
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        bubble = _Bubble(speaker, text)
        if speaker.lower() == "rey":
            row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignLeft)
            row.addStretch(1)
        else:
            row.addStretch(1)
            row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight)
        self._layout.insertLayout(self._layout.count() - 1, row)
        self._scroll_to_bottom()

    def set_partial(self, speaker: str, text: str) -> None:
        """Tampilkan/perbarui bubble sementara; teks kosong menghapusnya."""
        speaker = speaker.lower()
        text = text.strip()
        if not text:
            if self._live_speaker == speaker:
                self._remove_live()
            return

        if self._live_bubble is not None and self._live_speaker == speaker:
            self._live_bubble.set_text(text)
            self._scroll_to_bottom()
            return

        self._remove_live()
        self._empty.hide()

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        bubble = _Bubble(speaker, text)
        if speaker == "rey":
            row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignLeft)
            row.addStretch(1)
        else:
            row.addStretch(1)
            row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight)
        self._layout.insertLayout(self._layout.count() - 1, row)

        self._live_row = row
        self._live_bubble = bubble
        self._live_speaker = speaker
        self._scroll_to_bottom()

    def add_notice(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self._empty.hide()
        note = QLabel(text)
        note.setObjectName("EmptyHint")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setWordWrap(True)
        note.setContentsMargins(12, 2, 12, 2)
        self._layout.insertWidget(self._layout.count() - 1, note)
        self._scroll_to_bottom()

    def add_correction(self, original: str, better: str, note: str = "") -> None:
        self._empty.hide()
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(_CorrectionCard(original, better, note), 0, Qt.AlignmentFlag.AlignLeft)
        row.addStretch(1)
        self._layout.insertLayout(self._layout.count() - 1, row)
        self._scroll_to_bottom()

    def clear(self) -> None:
        self._live_row = None
        self._live_bubble = None
        self._live_speaker = None
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self._empty:
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())
        self._layout.insertWidget(0, self._empty)
        self._empty.show()

    def _remove_live(self) -> None:
        row = self._live_row
        self._live_row = None
        self._live_bubble = None
        self._live_speaker = None
        if row is None:
            return
        self._layout.removeItem(row)
        self._clear_layout(row)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(
            0,
            lambda: self.verticalScrollBar().setValue(
                self.verticalScrollBar().maximum()
            ),
        )
