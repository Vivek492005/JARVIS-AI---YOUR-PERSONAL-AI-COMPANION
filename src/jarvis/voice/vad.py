"""Voice activity detection + end-of-turn endpointing (Master Plan Task 3.3).

Fixes F-18: the old ``phrase_time_limit=6s`` cut long commands off.
Now speech start/stop comes from VAD with a 400-700 ms hangover, a
configurable 30 s max utterance, and *semantic* endpointing: if the
partial transcript ends on a connector word ("aur", "phir", "matlab",
"and", "so", ...), the hangover is extended because the user probably
isn't done.

Backends (lazy):
- ``webrtc`` — webrtcvad (tiny, CPU-cheap).
- ``silero`` — Silero VAD via torch (heavier, more accurate).
- ``energy`` — pure-Python energy gate with a *dynamic* noise floor
  (replaces the old static ``energy_threshold: 300``). Always available;
  used in tests and as the last-resort fallback.

Frames are 16-bit mono PCM at 16 kHz (see :mod:`jarvis.voice.audio`).
"""

from __future__ import annotations

import logging
import math
import struct
import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Protocol

logger = logging.getLogger(__name__)

# Connector words (Hindi + English): ending on one of these extends the
# hangover — the sentence is probably incomplete.
CONNECTOR_WORDS = frozenset(
    {
        "aur",
        "phir",
        "matlab",
        "lekin",
        "kyunki",
        "toh",
        "to",
        "phirbhi",
        "aur phir",
        "isliye",
        "magar",
        "par",
        "and",
        "so",
        "then",
        "but",
        "because",
        "uh",
        "um",
        "like",
        "you know",
    }
)


class VADBackend(Protocol):
    """Frame-level speech detector."""

    @property
    def name(self) -> str: ...

    def is_speech(self, frame: bytes, sample_rate: int = 16000) -> bool: ...


def _rms_db(frame: bytes) -> float:
    """RMS level of a 16-bit PCM frame in dBFS."""
    if not frame:
        return -96.0
    n = len(frame) // 2
    samples = struct.unpack(f"<{n}h", frame[: n * 2])
    if not samples:
        return -96.0
    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    if rms <= 0:
        return -96.0
    return 20.0 * math.log10(rms / 32768.0)


class EnergyVAD:
    """Energy gate with a dynamic noise floor.

    The floor tracks the quietest recent frames (slow attack, fast-ish
    release); speech = level > floor + margin_db. No static threshold.
    """

    def __init__(self, margin_db: float = 12.0, floor_attack: float = 0.02) -> None:
        self.margin_db = margin_db
        self.floor_attack = floor_attack
        self._floor_db = -60.0
        self._lock = threading.Lock()
        self.name = "energy"

    def is_speech(self, frame: bytes, sample_rate: int = 16000) -> bool:
        level = _rms_db(frame)
        with self._lock:
            # Track the floor downward quickly, upward slowly.
            if level < self._floor_db:
                self._floor_db = level
            else:
                self._floor_db += (level - self._floor_db) * self.floor_attack
            return level > self._floor_db + self.margin_db

    @property
    def floor_db(self) -> float:
        with self._lock:
            return self._floor_db


class WebRTCVADBackend:
    """webrtcvad wrapper (lazy import)."""

    def __init__(self, aggressiveness: int = 2) -> None:
        try:
            import webrtcvad
        except ImportError as e:
            raise RuntimeError(
                "webrtcvad is not installed. Install with "
                "`pip install jarvis-assistant[audio]` (see docs/AUDIO_SETUP.md)."
            ) from e
        self._vad = webrtcvad.Vad(aggressiveness)
        self.name = "webrtc"

    def is_speech(self, frame: bytes, sample_rate: int = 16000) -> bool:
        # webrtcvad wants 10/20/30 ms frames at 8/16/32/48 kHz.
        return bool(self._vad.is_speech(frame, sample_rate))


class SileroVADBackend:
    """Silero VAD wrapper (lazy torch import; heavier but more accurate)."""

    def __init__(self) -> None:
        try:
            import torch
        except ImportError as e:
            raise RuntimeError(
                "torch is not installed. Install with "
                "`pip install jarvis-assistant[audio-ml]` (see docs/AUDIO_SETUP.md)."
            ) from e
        self._torch = torch
        self._model, self._utils = torch.hub.load(
            "snakers4/silero-vad", "silero_vad", trust_repo=True
        )
        self.name = "silero"

    def is_speech(self, frame: bytes, sample_rate: int = 16000) -> bool:
        import numpy as np

        audio = np.frombuffer(frame, dtype=np.int16).astype("float32") / 32768.0
        tensor = self._torch.from_numpy(audio)
        with self._torch.no_grad():
            prob = self._model(tensor, sample_rate).item()
        return prob >= 0.5


@dataclass
class EndpointConfig:
    hangover_ms: int = 500  # silence after speech before end-of-turn
    hangover_extension_ms: int = 400  # extra when transcript ends on connector
    max_utterance_s: float = 30.0  # hard cap (plan: configurable)
    min_utterance_ms: int = 200  # ignore blips shorter than this


class Endpointer:
    """Turn-level endpointing over a VAD backend.

    Feed frames via :meth:`feed`; when an utterance ends,
    :meth:`take_utterance` returns ``(audio_bytes, duration_s)`` and the
    endpointer resets. ``partial_transcript`` (set by the STT layer) drives
    semantic hangover extension.
    """

    def __init__(
        self,
        vad: VADBackend,
        config: Optional[EndpointConfig] = None,
        clock: Optional[callable] = None,
    ) -> None:
        self.vad = vad
        self.config = config or EndpointConfig()
        self._clock = clock or time.monotonic
        self.partial_transcript = ""
        self._frames: List[bytes] = []
        self._speech_started_at: Optional[float] = None
        self._last_speech_at: Optional[float] = None
        self._done = False

    def feed(self, frame: bytes, sample_rate: int = 16000) -> bool:
        """Feed one frame. Returns True while the turn is still open."""
        now = self._clock()
        speech = self.vad.is_speech(frame, sample_rate)
        if speech:
            if self._speech_started_at is None:
                self._speech_started_at = now
            self._last_speech_at = now
            self._frames.append(frame)
            # Hard cap: very long utterances are cut at max_utterance_s.
            if now - self._speech_started_at >= self.config.max_utterance_s:
                self._done = True
            return not self._done
        # Silence.
        if self._speech_started_at is None:
            return True  # haven't started yet; keep listening
        hangover = self.config.hangover_ms / 1000.0
        if self._ends_on_connector():
            hangover += self.config.hangover_extension_ms / 1000.0
        silence = now - (self._last_speech_at or now)
        if silence >= hangover:
            # Ignore blips.
            dur_ms = (self._last_speech_at - self._speech_started_at) * 1000.0
            self._done = dur_ms >= self.config.min_utterance_ms
            if not self._done:
                self._reset()
        return not self._done

    def _ends_on_connector(self) -> bool:
        text = self.partial_transcript.strip().lower()
        if not text:
            return False
        last = text.split()[-1].rstrip(".,!?")
        return last in CONNECTOR_WORDS

    def take_utterance(self) -> Optional[tuple]:
        """Return (audio, duration_s) if a turn completed, else None."""
        if not self._done or self._speech_started_at is None:
            return None
        audio = b"".join(self._frames)
        duration = (self._last_speech_at or 0.0) - self._speech_started_at
        self._reset()
        return audio, duration

    def _reset(self) -> None:
        self._frames = []
        self._speech_started_at = None
        self._last_speech_at = None
        self._done = False
        self.partial_transcript = ""
