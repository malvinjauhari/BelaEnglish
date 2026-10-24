"""Sesi Gemini Live: audio dua arah, transkrip, barge-in, reconnect.

Alur singkat::

    mic 16 kHz ──► send_realtime_input ──► Gemini Live ──► audio 24 kHz ──► speaker
                                    └──► transkrip ──► EventBus ──► UI

Barge-in: mic tidak pernah dimatikan saat Rey bicara. Server memutus respons
sendiri (``START_OF_ACTIVITY_INTERRUPTS``) dan mengirim ``interrupted``; kita
kosongkan buffer output sehingga suara berhenti dalam ~10 ms.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import time

from google import genai
from google.genai import types

from ..config import Config
from .audio import OUTPUT_RATE, AudioIO
from .bus import EventBus
from .persona import build_system_instruction, greeting_prompt
from .state import AppState, Event, TurnStateMachine
from .transcript import TurnTranscript
from .visemes import EnvelopeAnalyzer

log = logging.getLogger("bela.live")

RETRY_BASE_S = 1.0
RETRY_MAX_S = 8.0


class LiveAgent:
    def __init__(self, config: Config, bus: EventBus, machine: TurnStateMachine) -> None:
        self.config = config
        self.bus = bus
        self.machine = machine

        self.audio = AudioIO(
            input_device=config.get("audio", "input_device", default=None),
            output_device=config.get("audio", "output_device", default=None),
        )

        primary = config.get("model", default="models/gemini-2.5-flash-native-audio-preview-12-2025")
        fallbacks = config.get("model_fallbacks", default=[]) or []
        self._models = list(dict.fromkeys([primary, *fallbacks]))
        self._model_index = 0

        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._session = None
        self._handle: str | None = None
        self._go_away = False

        self._muted = False
        self._greeted = False
        self._turn = TurnTranscript()
        self._out_analyzer = EnvelopeAnalyzer(OUTPUT_RATE)
        self._drain_task: asyncio.Task | None = None
        self._user_speech_end: float | None = None
        self._latency_reported = False

    # ── kontrol dari UI ───────────────────────────────────────────────────
    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def is_connected(self) -> bool:
        return self._session is not None

    @property
    def muted(self) -> bool:
        return self._muted

    async def start(self) -> None:
        if self.is_running:
            return
        if not self.config.has_api_key:
            message = "API key Gemini belum diisi. Buka ⚙ lalu tempel key-nya."
            self.bus.notice.emit(message)
            self.bus.error_occurred.emit(message)
            self.machine.handle(Event.RESET)
            return

        self._stop.clear()
        self._turn.reset()
        self._greeted = False
        self._muted = False
        self._latency_reported = False
        self._user_speech_end = None
        self.bus.session_changed.emit(True)
        self.machine.handle(Event.CONNECT)
        self._task = asyncio.create_task(self._run(), name="bela-live")

    async def stop(self) -> None:
        self._stop.set()
        self.audio.clear_audio()
        self.bus.level_changed.emit(0.0, "M")

        task = self._task
        if task is not None and not task.done():
            with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), timeout=3.0)
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._task = None
        self._session = None
        self._clear_partials()
        self.bus.session_changed.emit(False)
        self.machine.force(AppState.IDLE)

    def set_muted(self, muted: bool) -> None:
        self._muted = muted

    async def send_text(self, text: str) -> bool:
        text = text.strip()
        if not text:
            return False
        if self._session is None:
            self.bus.notice.emit("Belum tersambung. Klik tombol mic dulu.")
            return False

        self.bus.message_added.emit("you", text)
        self._user_speech_end = time.monotonic()
        self._latency_reported = False
        self.machine.handle(Event.THINK)
        try:
            await self._session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=text)]),
                turn_complete=True,
            )
        except Exception as exc:  # noqa: BLE001 (permukaan error SDK beragam)
            log.warning("send_text gagal: %s", exc)
            self.machine.force(AppState.IDLE)
            self.bus.notice.emit("Pesan tidak terkirim. Koneksi sedang dipulihkan.")
            return False
        return True

    # ── loop utama / reconnect ────────────────────────────────────────────
    async def _run(self) -> None:
        try:
            try:
                await self.audio.start()
            except Exception as exc:  # noqa: BLE001
                log.exception("audio start gagal")
                message = f"Mic/speaker tidak bisa dibuka: {exc}"
                self.bus.notice.emit(message)
                self.bus.error_occurred.emit(message)
                self.machine.force(AppState.ERROR)
                return

            delay = RETRY_BASE_S
            while not self._stop.is_set():
                try:
                    await self._connect_once()
                    if self._stop.is_set():
                        break
                    delay = RETRY_BASE_S
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    if self._stop.is_set():
                        break

                    kind, message = _describe_error(exc)
                    log.warning("live error (%s): %s", kind, exc)
                    self.bus.error_occurred.emit(message)
                    self.machine.force(AppState.ERROR)

                    if kind == "auth":
                        self.bus.notice.emit(
                            "API key ditolak. Perbaiki di ⚙ lalu mulai sesi lagi."
                        )
                        break
                    if kind == "missing" and self._model_index + 1 < len(self._models):
                        self._model_index += 1
                        self.bus.notice.emit(
                            f"Model tidak tersedia. Mencoba {self._models[self._model_index]}..."
                        )
                        continue
                    if kind == "quota":
                        delay = RETRY_MAX_S

                    wait = delay + random.uniform(0.0, 0.4)
                    self.bus.notice.emit(
                        f"{message} Mencoba lagi dalam {wait:.0f} detik."
                    )
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(self._stop.wait(), timeout=wait)
                    delay = min(delay * 2, RETRY_MAX_S)
        finally:
            if self._drain_task is not None:
                self._drain_task.cancel()
                self._drain_task = None
            self.audio.stop()
            self._session = None
            self._clear_partials()
            self.bus.level_changed.emit(0.0, "M")
            self.bus.session_changed.emit(False)
            self.machine.force(AppState.IDLE)

    async def _connect_once(self) -> None:
        model = self._models[self._model_index]
        self.machine.force(AppState.CONNECTING)
        self._go_away = False

        client = genai.Client(api_key=self.config.api_key)
        config = self._build_config()

        async with client.aio.live.connect(model=model, config=config) as session:
            self._session = session
            self._turn.reset()
            self.audio.drain_input()
            self.machine.handle(Event.READY)
            self.bus.notice.emit("Tersambung. Bicara kapan saja.")

            if (
                not self._greeted
                and self.config.get("session", "greet_on_connect", default=True)
            ):
                self._greeted = True
                await self._send_greeting(session)

            await self._run_session_tasks(session)

    async def _run_session_tasks(self, session) -> None:
        tasks = [
            asyncio.create_task(self._send_loop(session), name="bela-send"),
            asyncio.create_task(self._receive_loop(session), name="bela-recv"),
            asyncio.create_task(self._stop.wait(), name="bela-stop"),
        ]
        stop_task = tasks[-1]

        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        for task in pending:
            with contextlib.suppress(asyncio.CancelledError):
                await task

        if stop_task in done:
            return
        for task in done:
            if task is stop_task:
                continue
            exc = task.exception()
            if exc is not None:
                raise exc

    async def _send_loop(self, session) -> None:
        while not self._stop.is_set():
            data = await self.audio.read_input()
            if data is None:
                return
            if self._muted:
                continue
            await session.send_realtime_input(
                audio=types.Blob(data=data, mime_type="audio/pcm;rate=16000")
            )

    async def _receive_loop(self, session) -> None:
        async for message in session.receive():
            if self._stop.is_set():
                return
            self._handle_message(message)
        if self._go_away:
            return
        if not self._stop.is_set():
            raise ConnectionError("Sesi Live berakhir tanpa penutupan normal")

    # ── konfigurasi sesi ──────────────────────────────────────────────────
    def _build_config(self) -> types.LiveConnectConfig:
        audio = self.config.get("audio", default={}) or {}
        voice = self.config.get("voice", default="Kore")
        mode = self.machine.mode

        resumption = (
            types.SessionResumptionConfig(handle=self._handle)
            if self._handle
            else types.SessionResumptionConfig()
        )

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=build_system_instruction(self.config, mode),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
            realtime_input_config=types.RealtimeInputConfig(
                activity_handling=types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
                automatic_activity_detection=types.AutomaticActivityDetection(
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                    prefix_padding_ms=int(audio.get("prefix_padding_ms", 300)),
                    silence_duration_ms=int(audio.get("silence_ms", 650)),
                ),
                turn_coverage=types.TurnCoverage.TURN_INCLUDES_ONLY_ACTIVITY,
            ),
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow()
            ),
            session_resumption=resumption,
        )

    async def _send_greeting(self, session) -> None:
        name = (self.config.get("persona", "user_name", default="") or "").strip()
        self.machine.handle(Event.THINK)
        self._user_speech_end = time.monotonic()
        self._latency_reported = False
        try:
            await session.send_client_content(
                turns=types.Content(
                    role="user", parts=[types.Part(text=greeting_prompt(name))]
                ),
                turn_complete=True,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("greeting gagal: %s", exc)
            self.machine.force(AppState.IDLE)

    # ── penanganan pesan server ───────────────────────────────────────────
    def _handle_message(self, message: types.LiveServerMessage) -> None:
        update = message.session_resumption_update
        if update is not None and update.new_handle:
            self._handle = update.new_handle

        if message.go_away is not None:
            self._go_away = True
            self.bus.notice.emit("Sesi dipindahkan oleh server, menyambung ulang...")
            return

        if message.voice_activity is not None:
            self._on_voice_activity(message.voice_activity)

        content = message.server_content
        if content is None:
            return

        if content.interrupted:
            self._on_interrupted()

        model_turn = content.model_turn
        if model_turn and model_turn.parts:
            for part in model_turn.parts:
                inline = part.inline_data
                if inline is None or not inline.data:
                    continue
                mime = (inline.mime_type or "").lower()
                if mime.startswith("audio/pcm"):
                    self._on_model_audio(inline.data)

        if content.input_transcription and content.input_transcription.text:
            self._on_input_text(content.input_transcription.text)

        if content.interim_input_transcription and content.interim_input_transcription.text:
            interim = self._turn.set_interim(content.interim_input_transcription.text)
            if interim:
                self.bus.partial_transcript.emit("you", interim)

        if content.output_transcription and content.output_transcription.text:
            joined = self._turn.add_output(content.output_transcription.text)
            if joined:
                self.bus.partial_transcript.emit("rey", joined)

        if content.turn_complete:
            self._on_turn_complete()

    def _on_voice_activity(self, activity: types.VoiceActivity) -> None:
        kind = activity.voice_activity_type
        if kind == types.VoiceActivityType.ACTIVITY_START:
            self.machine.handle(Event.SPEECH_START)
            self._user_speech_end = None
        elif kind == types.VoiceActivityType.ACTIVITY_END:
            self._user_speech_end = time.monotonic()
            self._latency_reported = False
            self.machine.handle(Event.SPEECH_END)

    def _on_input_text(self, text: str) -> None:
        joined = self._turn.add_input(text)
        if not joined:
            return
        self.bus.partial_transcript.emit("you", joined)
        if self.machine.state is AppState.IDLE:
            self.machine.handle(Event.SPEECH_START)

    def _on_model_audio(self, data: bytes) -> None:
        self.audio.queue_audio(data)
        features = self._out_analyzer.feed(data)
        self.bus.level_changed.emit(features.level, features.shape)

        if self.machine.state in (
            AppState.IDLE,
            AppState.LISTENING,
            AppState.THINKING,
        ):
            self.machine.handle(Event.AUDIO_START)

        if self._user_speech_end is not None and not self._latency_reported:
            self._latency_reported = True
            elapsed = int((time.monotonic() - self._user_speech_end) * 1000)
            if 0 < elapsed < 15_000:
                self.bus.latency_reported.emit(elapsed)

    def _on_interrupted(self) -> None:
        self.audio.clear_audio()
        self.bus.level_changed.emit(0.0, "M")
        self._turn.clear_output()
        self.bus.partial_transcript.emit("rey", "")

        if self._drain_task is not None:
            self._drain_task.cancel()
            self._drain_task = None

        if self.machine.state in (AppState.SPEAKING, AppState.THINKING):
            self.machine.handle(Event.INTERRUPT)
            self.machine.handle(Event.SPEECH_START)

    def _on_turn_complete(self) -> None:
        user_text = self._turn.take_input()
        rey_text = self._turn.take_output()
        self._clear_partials()
        if user_text:
            self.bus.message_added.emit("you", user_text)
        if rey_text:
            self.bus.message_added.emit("rey", rey_text)
        self._turn.reset()

        if self._drain_task is not None:
            self._drain_task.cancel()
        self._drain_task = asyncio.create_task(self._drain_then_idle())

    async def _drain_then_idle(self) -> None:
        deadline = time.monotonic() + 2.5
        while self.audio.buffered_seconds > 0.08 and time.monotonic() < deadline:
            await asyncio.sleep(0.04)
        self.bus.level_changed.emit(0.0, "M")
        self.machine.handle(Event.AUDIO_END)

    def _clear_partials(self) -> None:
        self.bus.partial_transcript.emit("you", "")
        self.bus.partial_transcript.emit("rey", "")


def _describe_error(exc: Exception) -> tuple[str, str]:
    text = str(exc).lower()
    if (
        "api key" in text
        or "unauthenticated" in text
        or "permission_denied" in text
        or "1007" in text
    ):
        return "auth", "API key tidak valid atau tidak punya akses."
    if "not found" in text or "not_found" in text or "404" in text:
        return "missing", "Model Live tidak ditemukan."
    if (
        "quota" in text
        or "resource_exhausted" in text
        or "429" in text
        or "rate limit" in text
    ):
        return "quota", "Kuota atau rate limit tercapai."
    if (
        "unavailable" in text
        or "deadline" in text
        or "connection" in text
        or "websocket" in text
        or "network" in text
        or "sesi live berakhir" in text
    ):
        return "network", "Koneksi terputus."
    return "other", f"Terjadi kesalahan: {exc}"
