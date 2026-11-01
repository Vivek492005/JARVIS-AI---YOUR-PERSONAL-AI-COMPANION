"""FakeMic — streams PCM frames from a wav file, like a microphone would.

No audio hardware needed: tests synthesize a wav with
:py:meth:`FakeMic.synth_tone` (stdlib ``wave`` only) and stream it in
20 ms frames. ``frames()`` yields ``bytes`` until EOF.
"""

from __future__ import annotations

import math
import os
import struct
import tempfile
import wave
from typing import Iterator, Optional


class FakeMic:
    """Wav-backed fake microphone."""

    def __init__(self, wav_path: str, frame_ms: int = 20) -> None:
        self._wav = wave.open(wav_path, "rb")
        self.sample_rate = self._wav.getframerate()
        self.channels = self._wav.getnchannels()
        self.frame_bytes = int(self.sample_rate * self.channels * 2 * frame_ms / 1000)
        self.frames_read = 0

    @staticmethod
    def synth_tone(seconds: float = 0.5, freq: float = 440.0, sample_rate: int = 16000) -> str:
        """Write a temp wav with a sine blip; returns the path."""
        n = int(sample_rate * seconds)
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="fake-mic-")
        os.close(fd)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            frames = b"".join(
                struct.pack("<h", int(16000 * math.sin(2 * math.pi * freq * i / sample_rate)))
                for i in range(n)
            )
            w.writeframes(frames)
        return path

    def read_frame(self) -> Optional[bytes]:
        data = self._wav.readframes(self.frame_bytes // 2)
        if not data:
            return None
        self.frames_read += 1
        return data

    def frames(self) -> Iterator[bytes]:
        while True:
            frame = self.read_frame()
            if frame is None:
                break
            yield frame

    def close(self) -> None:
        self._wav.close()

    def __enter__(self) -> "FakeMic":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


__all__ = ["FakeMic"]
