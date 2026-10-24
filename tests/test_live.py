import asyncio

from google.genai import types

from app.config import Config
from app.core.bus import EventBus
from app.core.live import LiveAgent
from app.core.state import AppState, TurnStateMachine


def _agent(tmp_path):
    config = Config(path=tmp_path / "config.json")
    bus = EventBus()
    machine = TurnStateMachine()
    return LiveAgent(config, bus, machine), bus, machine


def _message(**content):
    return types.LiveServerMessage(
        server_content=types.LiveServerContent(**content)
    )


def _audio_turn(text: str = "") -> types.LiveServerMessage:
    return _message(
        model_turn=types.Content(
            parts=[
                types.Part(
                    inline_data=types.Blob(
                        data=b"\x00" * 4800, mime_type="audio/pcm;rate=24000"
                    )
                )
            ]
        ),
        output_transcription=types.Transcription(text=text) if text else None,
    )


def test_turn_complete_persists_both_sides(tmp_path):
    async def run():
        agent, bus, machine = _agent(tmp_path)
        messages: list[tuple[str, str]] = []
        partials: list[tuple[str, str]] = []
        levels: list[tuple[float, str]] = []
        latency: list[int] = []
        bus.message_added.connect(lambda s, t: messages.append((s, t)))
        bus.partial_transcript.connect(lambda s, t: partials.append((s, t)))
        bus.level_changed.connect(lambda level, shape: levels.append((level, shape)))
        bus.latency_reported.connect(latency.append)

        machine.handle("speech_start")
        machine.handle("speech_end")
        agent._user_speech_end = 1.0
        agent._latency_reported = False

        agent._handle_message(
            _message(
                input_transcription=types.Transcription(text="I go there yesterday"),
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
                output_transcription=types.Transcription(
                    text="Oh, you went there yesterday?"
                ),
                turn_complete=True,
            )
        )

        assert ("you", "I go there yesterday") in messages
        assert ("rey", "Oh, you went there yesterday?") in messages
        # live bubble dibersihkan setelah final
        assert partials[-2:] == [("you", ""), ("rey", "")]
        assert levels  # level audio dilaporkan ke UI
        assert agent.audio.buffered_seconds > 0

        # anggap speaker sudah selesai memutar buffer
        agent.audio.clear_audio()
        await asyncio.sleep(0.15)
        assert machine.state is AppState.IDLE

    asyncio.run(run())


def test_interrupt_flushes_audio_and_switches_to_listening(tmp_path):
    async def run():
        agent, bus, machine = _agent(tmp_path)
        partials: list[tuple[str, str]] = []
        bus.partial_transcript.connect(lambda s, t: partials.append((s, t)))

        machine.force(AppState.SPEAKING)
        agent.audio.queue_audio(b"\x00" * 24000)
        assert agent.audio.buffered_seconds > 0

        agent._handle_message(_message(interrupted=True))

        assert agent.audio.buffered_seconds == 0.0
        assert machine.state is AppState.LISTENING
        assert ("rey", "") in partials

    asyncio.run(run())


def test_voice_activity_drives_state(tmp_path):
    agent, _bus, machine = _agent(tmp_path)

    agent._handle_message(
        types.LiveServerMessage(
            voice_activity=types.VoiceActivity(
                voice_activity_type=types.VoiceActivityType.ACTIVITY_START
            )
        )
    )
    assert machine.state is AppState.LISTENING

    agent._handle_message(
        types.LiveServerMessage(
            voice_activity=types.VoiceActivity(
                voice_activity_type=types.VoiceActivityType.ACTIVITY_END
            )
        )
    )
    assert machine.state is AppState.THINKING
    assert agent._user_speech_end is not None
