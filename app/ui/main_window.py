"""Jendela utama BelaEnglish (M1: shell UI + karakter)."""

from __future__ import annotations

import time

from PyQt6.QtCore import QPoint, QSize, Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..core.bus import EventBus
from ..core.state import AppState, Mode, TurnStateMachine
from .avatar.stage import AvatarStage
from .settings import SettingsDialog
from .sidebar import ControlBar, MicOrb
from .transcript import TranscriptView

STATUS_TEXT = {
    AppState.CONNECTING: ("thinking", "MENYAMBUNG"),
    AppState.IDLE: ("idle", "SIAP"),
    AppState.LISTENING: ("listening", "MENDENGAR"),
    AppState.THINKING: ("thinking", "BERPIKIR"),
    AppState.SPEAKING: ("speaking", "BICARA"),
    AppState.INTERRUPTED: ("idle", "DISELA"),
    AppState.ERROR: ("error", "ERROR"),
}

MODE_META = {
    Mode.FREE_TALK: ("Free Talk", "Ngobrol bebas, topik dari kamu"),
    Mode.ROLEPLAY: ("Roleplay", "Main peran sesuai skenario"),
    Mode.DRILL: ("Drill", "Latihan satu pola, ulang sampai lancar"),
    Mode.REVIEW: ("Review", "Ulang kesalahan & kosakata lama"),
}

LEVEL_PERCENT = {"A2": 25, "B1": 50, "B2": 75, "C1": 95}


class TitleBar(QWidget):
    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self._window = window
        self._drag_offset: QPoint | None = None
        self.setObjectName("TitleBar")
        self.setFixedHeight(46)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 10, 0)
        layout.setSpacing(10)

        name = QLabel("BELA ENGLISH")
        name.setObjectName("AppName")
        layout.addWidget(name)

        self.status = QLabel("SIAP")
        self.status.setObjectName("StatusPill")
        self.status.setProperty("state", "idle")
        layout.addWidget(self.status)
        layout.addStretch(1)

        settings_button = QPushButton("⚙")
        settings_button.setObjectName("WinButton")
        settings_button.setFixedSize(32, 30)
        settings_button.setToolTip("Pengaturan")
        settings_button.clicked.connect(window._open_settings)  # noqa: SLF001
        layout.addWidget(settings_button)

        minimize = QPushButton("—")
        minimize.setObjectName("WinButton")
        minimize.setFixedSize(32, 30)
        minimize.clicked.connect(window.showMinimized)
        layout.addWidget(minimize)

        maximize = QPushButton("□")
        maximize.setObjectName("WinButton")
        maximize.setFixedSize(32, 30)
        maximize.clicked.connect(window._toggle_maximize)  # noqa: SLF001
        layout.addWidget(maximize)

        close = QPushButton("✕")
        close.setObjectName("WinButton")
        close.setProperty("danger", "true")
        close.setFixedSize(32, 30)
        close.clicked.connect(QApplication.instance().quit)
        layout.addWidget(close)

    # drag window tanpa frame
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        handle = self._window.windowHandle()
        if handle is not None and handle.startSystemMove():
            return
        self._drag_offset = event.globalPosition().toPoint() - self._window.pos()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None:
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, _event) -> None:  # noqa: N802
        self._drag_offset = None

    def mouseDoubleClickEvent(self, _event) -> None:  # noqa: N802
        self._window._toggle_maximize()  # noqa: SLF001


class MainWindow(QMainWindow):
    def __init__(self, config: Config, bus: EventBus) -> None:
        super().__init__()
        self.config = config
        self.bus = bus
        self.machine = TurnStateMachine()

        self.setWindowTitle("BelaEnglish")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(980, 640)
        self.resize(1180, 720)

        self._start = time.monotonic()

        self.root = QFrame()
        self.root.setObjectName("Root")
        self.setCentralWidget(self.root)

        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)

        self.titlebar = TitleBar(self)
        outer.addWidget(self.titlebar)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(16, 0, 16, 16)
        content_layout.setSpacing(16)
        outer.addWidget(content, 1)

        content_layout.addWidget(self._build_left(), 0)
        content_layout.addWidget(self._build_right(), 1)

        self._grip = QSizeGrip(self.root)
        self._grip.setFixedSize(16, 16)

        self._wire()
        self._apply_config()

        self._clock = QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._tick_clock)
        self._clock.start()

    # ── konstruksi UI ─────────────────────────────────────────────────────
    def _build_left(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setFixedWidth(372)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(4)

        self.stage = AvatarStage(panel)
        layout.addWidget(self.stage, 1)

        mic_row = QHBoxLayout()
        mic_row.addStretch(1)
        self.mic = MicOrb(panel)
        mic_row.addWidget(self.mic)
        mic_row.addStretch(1)
        layout.addLayout(mic_row)

        self.mic_hint = QLabel("Ctrl+Space untuk mute")
        self.mic_hint.setObjectName("StatName")
        self.mic_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.mic_hint)

        return panel

    def _build_right(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(12)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        self.scenario_title = QLabel("Free Talk")
        self.scenario_title.setObjectName("ScenarioTitle")
        self.scenario_meta = QLabel("Ngobrol bebas, topik dari kamu · B1")
        self.scenario_meta.setObjectName("ScenarioMeta")
        titles.addWidget(self.scenario_title)
        titles.addWidget(self.scenario_meta)
        header.addLayout(titles)
        header.addStretch(1)

        self.timer_label = QLabel("00:00")
        self.timer_label.setObjectName("StatValue")
        header.addWidget(self.timer_label)
        layout.addLayout(header)

        self.controls = ControlBar(panel)
        layout.addWidget(self.controls)

        transcript_panel = QFrame()
        transcript_panel.setObjectName("Panel")
        transcript_layout = QVBoxLayout(transcript_panel)
        transcript_layout.setContentsMargins(6, 6, 6, 6)
        self.transcript = TranscriptView(transcript_panel)
        transcript_layout.addWidget(self.transcript)
        layout.addWidget(transcript_panel, 1)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self.input = QLineEdit()
        self.input.setObjectName("InputBar")
        self.input.setPlaceholderText("Input teks & suara aktif di tahap M2")
        self.input.setEnabled(False)
        self.input.returnPressed.connect(self._on_text_submit)
        input_row.addWidget(self.input, 1)

        self.send_button = QPushButton("Kirim")
        self.send_button.setObjectName("Primary")
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self._on_text_submit)
        input_row.addWidget(self.send_button)
        layout.addLayout(input_row)

        return panel

    # ── wiring ────────────────────────────────────────────────────────────
    def _wire(self) -> None:
        self.machine.subscribe(lambda _old, new: self.bus.state_changed.emit(new.value))
        self.machine.subscribe_mode(lambda _old, new: self.bus.mode_changed.emit(new.value))

        self.bus.state_changed.connect(self._on_state)
        self.bus.mode_changed.connect(self._on_mode)
        self.bus.message_added.connect(self.transcript.add_message)
        self.bus.correction_added.connect(self.transcript.add_correction)
        self.bus.emotion_changed.connect(self.stage.set_emotion)
        self.bus.level_changed.connect(self._on_level)
        self.bus.muted_changed.connect(self._on_muted)

        self.controls.mode_changed.connect(self._on_mode_clicked)
        self.mic.muted_changed.connect(self.bus.muted_changed.emit)
        self.mic.clicked.connect(lambda: self.stage.force_blink())

        QShortcut(QKeySequence("Ctrl+Space"), self).activated.connect(self.mic.toggle)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.close)

        self._on_state(AppState.IDLE.value)

    def _apply_config(self) -> None:
        level = self.config.get("persona", "cefr_level", default="B1")
        self.controls.set_mode(self.machine.mode.value)
        self._set_level_label(level)

        if self.config.get("ui", "always_on_top", default=False):
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

    def _set_level_label(self, level: str) -> None:
        self.scenario_meta.setText(f"{MODE_META[self.machine.mode][1]} · {level}")

    # ── event handler ─────────────────────────────────────────────────────
    def _on_state(self, state_value: str) -> None:
        try:
            state = AppState(state_value)
        except ValueError:
            return
        self.stage.set_state(state.value)
        key, text = STATUS_TEXT.get(state, ("idle", state.value.upper()))
        self.titlebar.status.setText(text)
        self.titlebar.status.setProperty("state", key)
        self.titlebar.status.style().unpolish(self.titlebar.status)
        self.titlebar.status.style().polish(self.titlebar.status)

    def _on_mode(self, mode_value: str) -> None:
        try:
            mode = Mode(mode_value)
        except ValueError:
            return
        title, meta = MODE_META[mode]
        level = self.config.get("persona", "cefr_level", default="B1")
        self.scenario_title.setText(title)
        self.scenario_meta.setText(f"{meta} · {level}")
        self.controls.set_mode(mode.value)

    def _on_mode_clicked(self, mode_value: str) -> None:
        self.machine.set_mode(mode_value)

    def _on_level(self, level: float) -> None:
        self.stage.set_audio("A", level)
        self.mic.set_level(level)

    def _on_muted(self, muted: bool) -> None:
        self.mic_hint.setText(
            "Mute aktif · Ctrl+Space" if muted else "Ctrl+Space untuk mute"
        )

    def _on_text_submit(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if not dialog.exec():
            return
        values = dialog.values()
        self.config.set(values["user_name"], "persona", "user_name")
        self.config.set(values["cefr_level"], "persona", "cefr_level")
        self.config.set(values["spice_level"], "persona", "spice_level")
        self.config.set(values["correction_level"], "persona", "correction_level")
        self.config.set(values["indonesian_help"], "persona", "indonesian_help")
        self.config.set(values["always_on_top"], "ui", "always_on_top")
        self.config.save()

        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(values["always_on_top"]))
        self.show()
        self._set_level_label(values["cefr_level"])

    # ── window ────────────────────────────────────────────────────────────
    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self.root.setProperty("maximized", self.isMaximized())
        self.root.style().unpolish(self.root)
        self.root.style().polish(self.root)
        self._grip.setVisible(not self.isMaximized())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._grip.move(self.root.width() - 18, self.root.height() - 18)
        self._grip.raise_()

    def _tick_clock(self) -> None:
        elapsed = int(time.monotonic() - self._start)
        minutes, seconds = divmod(elapsed, 60)
        self.timer_label.setText(f"{minutes:02d}:{seconds:02d}")

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(1180, 720)

    @property
    def muted(self) -> bool:
        return self.mic.muted
