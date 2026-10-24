"""Uji loop sesi penuh dengan klien Gemini palsu (tanpa jaringan/audio nyata)."""

import asyncio
import time

from google.genai import types

import app.core.live as live_mod
from app.config import Config
from app.core.bus import EventBus
from app.core.live import LiveAgent
from app.core.state import TurnStateMachine


class FakeSession:
    def __init__(self) -> None:
        self.audio_sent: list = []
        self.client_contents: list = []
        self.incoming: asyncio.Queue = asyncio.Queue()

    async def send_realtime_input(self, audio=None, **_kwargs) -> None:
        self.audio_sent.append(audio)

    async def send_client_content(self, turns=None, turn_complete=True) -> None:
        self.client_contents.append(turns)

    async def receive(self):
        while True:
            message = await self.incoming.get()
            if message is None:
                return
            yield message


class FakeConnect:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, *_exc) -> bool:
        return False


class FakeAioLive:
    def __init__(self, holder: dict) -> None:
        self.holder = holder

    def connect(self, model: str, config) -> FakeConnect:
        self.holder["models"].append(model)
        self.holder["configs"].append(config)
        session = FakeSession()
        self.holder["sessions"].append(session)
        return FakeConnect(session)


class FakeAio:
    def __init__(self, holder: dict) -> None:
        self.live = FakeAioLive(holder)


class FakeClient:
    def __init__(self, holder: dict, api_key: str) -> None:
        self.api_key = api_key
        self.aio = FakeAio(holder)


def _setup(tmp_path, monkeypatch):
    holder: dict = {"models": [], "configs": [], "sessions": []}
    monkeypatch.setattr(
        live_mod.genai,
        "Client",
        lambda api_key: FakeClient(holder, api_key),
    )
    monkeypatch.setattr(live_mod, "RETRY_BASE_S", 0.05)
    monkeypatch.setattr(live_mod, "RETRY_MAX_S", 0.05)

    config = Config(path=tmp_path / "config.json")
    config.set("fake-key", "gemini_api_key")
    bus = EventBus()
    machine = TurnStateMachine()
    agent = LiveAgent(config, bus, machine)

    async def fake_start() -> None:
        return None

    def fake_stop() -> None:
        return None

    async def fake_read() -> bytes:
        await asyncio.sleep(0.01)
        return b"\x00" * 2048

    monkeypatch.setattr(agent.audio, "start", fake_start)
    monkeypatch.setattr(agent.audio, "stop", fake_stop)
    monkeypatch.setattr(agent.audio, "read_input", fake_read)

    events: dict[str, list] = {
        "messages": [],
        "partials": [],
        "levels": [],
        "notices": [],
        "session": [],
    }
    bus.message_added.connect(lambda s, t: events["messages"].append((s, t)))
    bus.partial_transcript.connect(lambda s, t: events["partials"].append((s, t)))
    bus.level_changed.connect(lambda level, shape: events["levels"].append(level))
    bus.notice.connect(events["notices"].append)
    bus.session_changed.connect(events["session"].append)

    return agent, holder, events


async def _wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("kondisi tidak tercapai sebelum timeout")


def test_full_session_flow(tmp_path, monkeypatch):
    async def run():
        agent, holder, events = _setup(tmp_path, monkeypatch)

        await agent.start()
        await _wait_until(lambda: holder["sessions"] and holder["sessions"][0].client_contents)

        session = holder["sessions"][0]
        assert holder["models"] == ["models/gemini-2.5-flash-native-audio-preview-12-2025"]
        assert holder["configs"][0].speech_config.voice_config.prebuilt_voice_config.voice_name == "Kore"
        assert agent.is_connected
        # sapaan otomatis terkirim
        assert session.client_contents[0].role == "user"

        # frame mic terkirim ke server
        await _wait_until(lambda: session.audio_sent)
        blob = session.audio_sent[0]
        assert blob.mime_type.startswith("audio/pcm")
        assert len(blob.data) == 2048

        await session.incoming.put(
            types.LiveServerMessage(
                server_content=types.LiveServerContent(
                    input_transcription=types.Transcription(text="I want a coffee"),
                )
            )
        )
        await session.incoming.put(
            types.LiveServerMessage(
                server_content=types.LiveServerContent(
                    model_turn=types.Content(
                        parts=[
                            types.Part(
                                inline_data=types.Blob(
                                    data=b"\x00" * 4800,
                                    mime_type="audio/pcm;rate=24000",
                                )
                            )
                        ]
                    ),
                    output_transcription=types.Transcription(text="Sure, one coffee."),
                )
            )
        )
        await session.incoming.put(
            types.LiveServerMessage(
                server_content=types.LiveServerContent(turn_complete=True)
            )
        )

        await _wait_until(lambda: ("rey", "Sure, one coffee.") in events["messages"])
        assert ("you", "I want a coffee") in events["messages"]
        assert events["levels"]
        assert agent.audio.buffered_seconds > 0

        agent.audio.clear_audio()
        await agent.stop()

        assert not agent.is_running
        assert agent.machine.state is live_mod.AppState.IDLE
        assert events["session"][0] is True
        assert events["session"][-1] is False
        assert ("you", "") in events["partials"]

    asyncio.run(run())


def test_session_drop_triggers_reconnect(tmp_path, monkeypatch):
    async def run():
        agent, holder, events = _setup(tmp_path, monkeypatch)
        await agent.start()
        await _wait_until(lambda: len(holder["sessions"]) == 1)

        # server menutup stream tanpa go_away -> harus reconnect
        await holder["sessions"][0].incoming.put(None)
        await _wait_until(lambda: len(holder["sessions"]) >= 2, timeout=3.0)
        assert any("Koneksi" in notice or "kesalahan" in notice for notice in events["notices"])

        await agent.stop()
        assert not agent.is_running

    asyncio.run(run())
