"""State machine percakapan — murni Python, tanpa dependensi Qt.

Dipakai oleh pipeline audio (M2) dan animasi karakter (M1). Semua transisi
yang tidak dikenal diabaikan, bukan melempar exception, supaya event dari
server yang datang tidak berurutan tidak mematikan aplikasi.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum


class AppState(StrEnum):
    CONNECTING = "connecting"
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ERROR = "error"


class Mode(StrEnum):
    FREE_TALK = "free_talk"
    ROLEPLAY = "roleplay"
    DRILL = "drill"
    REVIEW = "review"


class Event(StrEnum):
    CONNECT = "connect"
    READY = "ready"
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    THINK = "think"
    AUDIO_START = "audio_start"
    AUDIO_END = "audio_end"
    INTERRUPT = "interrupt"
    ERROR_EVENT = "error"
    RESET = "reset"


TRANSITIONS: dict[tuple[AppState, Event], AppState] = {
    # koneksi
    (AppState.CONNECTING, Event.READY): AppState.IDLE,
    (AppState.CONNECTING, Event.ERROR_EVENT): AppState.ERROR,
    (AppState.CONNECTING, Event.RESET): AppState.IDLE,
    # idle
    (AppState.IDLE, Event.CONNECT): AppState.CONNECTING,
    (AppState.IDLE, Event.SPEECH_START): AppState.LISTENING,
    (AppState.IDLE, Event.ERROR_EVENT): AppState.ERROR,
    # mendengar
    (AppState.LISTENING, Event.SPEECH_END): AppState.THINKING,
    (AppState.LISTENING, Event.THINK): AppState.THINKING,
    (AppState.LISTENING, Event.INTERRUPT): AppState.IDLE,
    (AppState.LISTENING, Event.ERROR_EVENT): AppState.ERROR,
    (AppState.LISTENING, Event.RESET): AppState.IDLE,
    # berpikir (tool call / menunggu model)
    (AppState.THINKING, Event.AUDIO_START): AppState.SPEAKING,
    (AppState.THINKING, Event.AUDIO_END): AppState.IDLE,
    (AppState.THINKING, Event.SPEECH_START): AppState.LISTENING,
    (AppState.THINKING, Event.ERROR_EVENT): AppState.ERROR,
    (AppState.THINKING, Event.RESET): AppState.IDLE,
    # bicara
    (AppState.SPEAKING, Event.AUDIO_END): AppState.IDLE,
    (AppState.SPEAKING, Event.INTERRUPT): AppState.INTERRUPTED,
    (AppState.SPEAKING, Event.SPEECH_START): AppState.INTERRUPTED,
    (AppState.SPEAKING, Event.ERROR_EVENT): AppState.ERROR,
    # terinterupsi (barge-in)
    (AppState.INTERRUPTED, Event.SPEECH_START): AppState.LISTENING,
    (AppState.INTERRUPTED, Event.SPEECH_END): AppState.THINKING,
    (AppState.INTERRUPTED, Event.AUDIO_END): AppState.IDLE,
    (AppState.INTERRUPTED, Event.RESET): AppState.IDLE,
    (AppState.INTERRUPTED, Event.ERROR_EVENT): AppState.ERROR,
    # error
    (AppState.ERROR, Event.RESET): AppState.IDLE,
    (AppState.ERROR, Event.CONNECT): AppState.CONNECTING,
}

Listener = Callable[[AppState, AppState], None]


class TurnStateMachine:
    """Mesin state tunggal untuk satu sesi percakapan."""

    def __init__(self, initial: AppState = AppState.IDLE) -> None:
        self._state = initial
        self._mode = Mode.FREE_TALK
        self._listeners: list[Listener] = []
        self._mode_listeners: list[Callable[[Mode, Mode], None]] = []
        self.last_rejected: tuple[AppState, Event] | None = None

    # ── state ─────────────────────────────────────────────────────────────
    @property
    def state(self) -> AppState:
        return self._state

    @property
    def mode(self) -> Mode:
        return self._mode

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def subscribe_mode(self, listener: Callable[[Mode, Mode], None]) -> None:
        self._mode_listeners.append(listener)

    def handle(self, event: Event | str) -> AppState:
        """Terapkan event; kembalikan state sekarang."""
        try:
            event = Event(event)
        except ValueError:
            self.last_rejected = (self._state, event)  # type: ignore[assignment]
            return self._state

        target = TRANSITIONS.get((self._state, event))
        if target is None or target == self._state:
            self.last_rejected = (self._state, event)
            return self._state

        self._set_state(target)
        return self._state

    def force(self, state: AppState | str) -> AppState:
        """Paksa state (dipakai tombol reset). Tetap memberi tahu listener."""
        state = AppState(state)
        if state != self._state:
            self._set_state(state)
        return self._state

    def reset(self) -> AppState:
        return self.force(AppState.IDLE)

    def _set_state(self, target: AppState) -> None:
        previous, self._state = self._state, target
        self.last_rejected = None
        for listener in self._listeners:
            listener(previous, target)

    # ── mode ──────────────────────────────────────────────────────────────
    def set_mode(self, mode: Mode | str) -> Mode:
        mode = Mode(mode)
        if mode == self._mode:
            return self._mode
        previous, self._mode = self._mode, mode
        for listener in self._mode_listeners:
            listener(previous, mode)
        return self._mode
