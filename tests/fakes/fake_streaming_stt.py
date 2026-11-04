"""FakeStreamingSTT — scripted partials then a final, no hardware."""

from __future__ import annotations

from typing import Iterator, List

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from jarvis.voice.stt import Transcription  # noqa: E402


class FakeStreamingSTT:
    """Yields scripted partials per frame-batch, then one final."""

    name = "fake-streaming"
    offline_capable = True
    supports_streaming = True

    def __init__(self, partials: List[str], final: str) -> None:
        self._partials = partials
        self._final = final

    def transcribe(
        self, audio: bytes, language: str = "hi-en", sample_rate: int = 16000
    ) -> Transcription:
        return Transcription(text=self._final, confidence=1.0, language=language, engine=self.name)

    def stream(
        self, frames: Iterator[bytes], language: str = "hi-en", sample_rate: int = 16000
    ) -> Iterator[Transcription]:
        n = 0
        for _ in frames:
            if n < len(self._partials):
                yield Transcription(
                    text=self._partials[n],
                    confidence=0.5,
                    language=language,
                    is_final=False,
                    engine=self.name,
                )
            n += 1
        yield Transcription(
            text=self._final, confidence=1.0, language=language, is_final=True, engine=self.name
        )
