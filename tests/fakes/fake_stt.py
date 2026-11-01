"""FakeSTT — scripted speech-to-text.

Pops one transcript per ``transcribe()`` call, so a test can script a
whole conversation. Raises ``StopIteration`` when the script runs out
(tests should script exactly what they need).
"""

from __future__ import annotations

from typing import List


class FakeSTT:
    """Deterministic stand-in for any STTProvider."""

    def __init__(self, transcripts: List[str], name: str = "fake-stt") -> None:
        self._name = name
        self._transcripts = list(transcripts)
        self.calls: List[dict] = []

    @property
    def name(self) -> str:
        return self._name

    def transcribe(self, audio: bytes, language: str = "hi-en") -> str:
        self.calls.append({"bytes": len(audio or b""), "language": language})
        if not self._transcripts:
            raise StopIteration("FakeSTT script exhausted")
        return self._transcripts.pop(0)

    @property
    def exhausted(self) -> bool:
        return not self._transcripts


__all__ = ["FakeSTT"]
