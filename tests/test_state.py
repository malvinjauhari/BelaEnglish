from app.core.state import AppState, Event, Mode, TurnStateMachine


def test_starts_idle():
    machine = TurnStateMachine()
    assert machine.state is AppState.IDLE
    assert machine.mode is Mode.FREE_TALK


def test_full_turn_cycle():
    machine = TurnStateMachine()
    assert machine.handle(Event.SPEECH_START) is AppState.LISTENING
    assert machine.handle(Event.SPEECH_END) is AppState.THINKING
    assert machine.handle(Event.AUDIO_START) is AppState.SPEAKING
    assert machine.handle(Event.AUDIO_END) is AppState.IDLE


def test_barge_in_flow():
    machine = TurnStateMachine()
    machine.handle(Event.SPEECH_START)
    machine.handle(Event.SPEECH_END)
    machine.handle(Event.AUDIO_START)
    assert machine.state is AppState.SPEAKING

    assert machine.handle(Event.INTERRUPT) is AppState.INTERRUPTED
    # user langsung lanjut bicara setelah menyela
    assert machine.handle(Event.SPEECH_START) is AppState.LISTENING


def test_invalid_event_is_ignored():
    machine = TurnStateMachine()
    assert machine.handle(Event.AUDIO_END) is AppState.IDLE
    assert machine.last_rejected == (AppState.IDLE, Event.AUDIO_END)


def test_unknown_event_string_is_ignored():
    machine = TurnStateMachine()
    assert machine.handle("tidak-ada") is AppState.IDLE


def test_listener_fires_only_on_change():
    machine = TurnStateMachine()
    seen: list[tuple[AppState, AppState]] = []
    machine.subscribe(lambda old, new: seen.append((old, new)))

    machine.handle(Event.SPEECH_START)
    machine.handle(Event.AUDIO_END)  # tidak valid, tidak boleh memicu
    machine.handle(Event.SPEECH_END)

    assert seen == [
        (AppState.IDLE, AppState.LISTENING),
        (AppState.LISTENING, AppState.THINKING),
    ]


def test_error_and_recovery():
    machine = TurnStateMachine()
    assert machine.handle(Event.ERROR_EVENT) is AppState.ERROR
    assert machine.handle(Event.RESET) is AppState.IDLE


def test_mode_change_notifies_once():
    machine = TurnStateMachine()
    events: list[tuple[Mode, Mode]] = []
    machine.subscribe_mode(lambda old, new: events.append((old, new)))

    machine.set_mode("roleplay")
    machine.set_mode("roleplay")  # idempotent

    assert machine.mode is Mode.ROLEPLAY
    assert events == [(Mode.FREE_TALK, Mode.ROLEPLAY)]


def test_force_and_reset():
    machine = TurnStateMachine()
    machine.handle(Event.SPEECH_START)
    assert machine.force(AppState.SPEAKING) is AppState.SPEAKING
    assert machine.reset() is AppState.IDLE
