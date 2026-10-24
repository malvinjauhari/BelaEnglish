"""I/O audio PortAudio: mic 16 kHz masuk, speaker 24 kHz keluar.

Modul ini sengaja tidak mengimpor ``sounddevice`` di level atas supaya test dan
UI tetap bisa jalan di mesin tanpa PortAudio.

Desain barge-in: output memakai callback dengan buffer sendiri (``PcmBuffer``).
Saat server mengirim ``interrupted``, buffer dikosongkan dan suara berhenti
dalam satu periode callback (~10 ms), tanpa perlu menutup stream.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading

INPUT_RATE = 16_000
OUTPUT_RATE = 24_000
CHANNELS = 1
SAMPLE_WIDTH = 2  # int16
INPUT_BLOCK = 1024  # ~64 ms
OUTPUT_BLOCK = 480  # 10 ms @ 24 kHz
MAX_OUTPUT_SECONDS = 6.0


class PcmBuffer:
    """Buffer byte PCM yang aman dipakai dari thread callback PortAudio."""

    def __init__(self, max_bytes: int = OUTPUT_RATE * SAMPLE_WIDTH * 6) -> None:
        self._lock = threading.Lock()
        self._data = bytearray()
        self._max = max(1, max_bytes)

    def push(self, data: bytes) -> None:
        if not data:
            return
        with self._lock:
            self._data.extend(data)
            overflow = len(self._data) - self._max
            if overflow > 0:
                del self._data[:overflow]

    def fill(self, out: memoryview) -> int:
        """Isi ``out`` dari buffer; sisanya nol. Kembalikan byte yang terisi."""
        size = len(out)
        with self._lock:
            take = min(size, len(self._data))
            if take:
                out[:take] = self._data[:take]
                del self._data[:take]
        if take < size:
            out[take:] = b"\x00" * (size - take)
        return take

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    @property
    def buffered_seconds(self) -> float:
        with self._lock:
            return len(self._data) / float(OUTPUT_RATE * SAMPLE_WIDTH)


class AudioIO:
    """Mic + speaker dengan jembatan ke asyncio."""

    def __init__(
        self,
        input_device: int | str | None = None,
        output_device: int | str | None = None,
    ) -> None:
        self.input_device = input_device
        self.output_device = output_device

        self._loop: asyncio.AbstractEventLoop | None = None
        self._in_queue: asyncio.Queue[bytes | None] | None = None
        self._out = PcmBuffer(OUTPUT_RATE * SAMPLE_WIDTH * int(MAX_OUTPUT_SECONDS))
        self._in_stream = None
        self._out_stream = None
        self._running = False

    # ── lifecycle ─────────────────────────────────────────────────────────
    async def start(self) -> None:
        if self._running:
            return
        import sounddevice as sd  # impor lambat, lihat docstring modul

        self._loop = asyncio.get_running_loop()
        self._in_queue = asyncio.Queue(maxsize=120)

        self._in_stream = sd.RawInputStream(
            samplerate=INPUT_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=INPUT_BLOCK,
            device=self.input_device,
            callback=self._on_input,
        )
        self._out_stream = sd.RawOutputStream(
            samplerate=OUTPUT_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=OUTPUT_BLOCK,
            device=self.output_device,
            callback=self._on_output,
        )
        self._in_stream.start()
        self._out_stream.start()
        self._running = True

    def stop(self) -> None:
        self._running = False
        for stream in (self._in_stream, self._out_stream):
            if stream is None:
                continue
            with contextlib.suppress(Exception):
                stream.stop()
            with contextlib.suppress(Exception):
                stream.close()
        self._in_stream = None
        self._out_stream = None

        queue, loop = self._in_queue, self._loop
        if queue is not None and loop is not None and not loop.is_closed():
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(self._push_sentinel)

    def _push_sentinel(self) -> None:
        queue = self._in_queue
        if queue is None:
            return
        with contextlib.suppress(asyncio.QueueFull):
            queue.put_nowait(None)

    # ── input ─────────────────────────────────────────────────────────────
    def _on_input(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        loop, queue = self._loop, self._in_queue
        if loop is None or queue is None or not self._running:
            return
        data = bytes(indata)
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(self._push_input, data)

    def _push_input(self, data: bytes) -> None:
        queue = self._in_queue
        if queue is None:
            return
        if queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
        with contextlib.suppress(asyncio.QueueFull):
            queue.put_nowait(data)

    async def read_input(self) -> bytes | None:
        """Kembalikan frame PCM 16 kHz, atau ``None`` saat stream ditutup."""
        queue = self._in_queue
        if queue is None:
            return None
        return await queue.get()

    def drain_input(self) -> None:
        """Buang frame mic yang menumpuk (dipanggil saat reconnect)."""
        queue = self._in_queue
        if queue is None:
            return
        while True:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                return

    # ── output ────────────────────────────────────────────────────────────
    def _on_output(self, outdata, frames, time_info, status) -> None:  # noqa: ARG002
        view = memoryview(outdata).cast("B")
        self._out.fill(view)

    def queue_audio(self, data: bytes) -> None:
        self._out.push(data)

    def clear_audio(self) -> None:
        self._out.clear()

    @property
    def buffered_seconds(self) -> float:
        return self._out.buffered_seconds

    @property
    def running(self) -> bool:
        return self._running
