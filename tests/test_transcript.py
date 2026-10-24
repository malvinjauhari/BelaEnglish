from app.core.transcript import TurnTranscript


def test_incremental_chunks_are_joined():
    turn = TurnTranscript()
    assert turn.add_input("I") == "I"
    assert turn.add_input("went") == "I went"
    assert turn.add_input("home") == "I went home"
    assert turn.take_input() == "I went home"
    assert turn.input_text == ""


def test_cumulative_chunks_replace_instead_of_duplicating():
    turn = TurnTranscript()
    turn.add_input("I went")
    assert turn.add_input("I went to the market") == "I went to the market"
    assert turn.take_input() == "I went to the market"


def test_repeated_chunk_is_ignored():
    turn = TurnTranscript()
    turn.add_output("Hey there.")
    turn.add_output("Hey there.")
    assert turn.output_text == "Hey there."


def test_interim_is_replaced_by_final():
    turn = TurnTranscript()
    assert turn.set_interim("I wan") == "I wan"
    assert turn.add_input("I want coffee") == "I want coffee"
    assert turn.interim == ""


def test_output_can_be_discarded_after_interrupt():
    turn = TurnTranscript()
    turn.add_output("So the thing is")
    turn.clear_output()
    assert turn.output_text == ""
    turn.add_output("Okay, listen")
    assert turn.output_text == "Okay, listen"


def test_reset_clears_everything():
    turn = TurnTranscript()
    turn.add_input("hello")
    turn.add_output("hi")
    turn.set_interim("hel")
    turn.reset()
    assert turn.input_text == ""
    assert turn.output_text == ""
    assert turn.interim == ""
