from app.core.audio import PcmBuffer


def test_fill_takes_available_bytes_and_pads_silence():
    buf = PcmBuffer(max_bytes=100)
    buf.push(b"\x01\x02")

    out = memoryview(bytearray(6))
    assert buf.fill(out) == 2
    assert bytes(out) == b"\x01\x02\x00\x00\x00\x00"
    assert buf.buffered_seconds == 0.0


def test_clear_drops_buffered_audio():
    buf = PcmBuffer(max_bytes=48000)
    buf.push(b"\x00" * 24000)
    assert buf.buffered_seconds == 0.5

    buf.clear()
    assert buf.buffered_seconds == 0.0


def test_overflow_keeps_newest_audio():
    buf = PcmBuffer(max_bytes=4)
    buf.push(b"abcd")
    buf.push(b"ef")

    out = memoryview(bytearray(4))
    assert buf.fill(out) == 4
    assert bytes(out) == b"cdef"


def test_second_fill_is_silence():
    buf = PcmBuffer()
    buf.push(b"\x10\x20")
    first = memoryview(bytearray(2))
    second = memoryview(bytearray(2))

    assert buf.fill(first) == 2
    assert buf.fill(second) == 0
    assert bytes(first) == b"\x10\x20"
    assert bytes(second) == b"\x00\x00"
