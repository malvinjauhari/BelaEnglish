"""Penggabung potongan transkrip per turn — murni Python, mudah diuji.

Gemini mengirim transkrip bertahap. Kadang potongan bersifat tambahan
("I went"), kadang kumulatif ("I went to the market"). Kelas ini menormalkan
keduanya supaya UI tidak menampilkan teks ganda.
"""

from __future__ import annotations


class TurnTranscript:
    def __init__(self) -> None:
        self._input: list[str] = []
        self._output: list[str] = []
        self._interim = ""

    # ── input user ────────────────────────────────────────────────────────
    def add_input(self, text: str) -> str:
        joined = self._append(self._input, text)
        if text.strip():
            self._interim = ""
        return joined

    def set_interim(self, text: str) -> str:
        self._interim = text.strip()
        return self._interim

    @property
    def interim(self) -> str:
        return self._interim

    @property
    def input_text(self) -> str:
        return " ".join(self._input).strip()

    def take_input(self) -> str:
        text = self.input_text
        self._input.clear()
        self._interim = ""
        return text

    # ── output Rey ────────────────────────────────────────────────────────
    def add_output(self, text: str) -> str:
        return self._append(self._output, text)

    @property
    def output_text(self) -> str:
        return " ".join(self._output).strip()

    def take_output(self) -> str:
        text = self.output_text
        self._output.clear()
        return text

    def clear_output(self) -> None:
        self._output.clear()

    # ── util ──────────────────────────────────────────────────────────────
    def reset(self) -> None:
        self._input.clear()
        self._output.clear()
        self._interim = ""

    @staticmethod
    def _append(chunks: list[str], text: str) -> str:
        piece = text.strip()
        if not piece:
            return " ".join(chunks).strip()

        joined = " ".join(chunks).strip()
        if piece == joined or (chunks and piece == chunks[-1]):
            return joined
        if joined and piece.startswith(joined):
            # potongan kumulatif: ganti seluruh isi
            chunks[:] = [piece]
            return piece
        chunks.append(piece)
        return " ".join(chunks).strip()
