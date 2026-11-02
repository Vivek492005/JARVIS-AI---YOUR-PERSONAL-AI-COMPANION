"""Sound design (Master Plan Task 7.5).

Pleasant two-tone earcons synthesized with the stdlib ``wave`` module —
no dependencies, no binary assets in the repo. Generated once into the
per-install data dir, then played back.

The five canonical earcons: wake, thinking_start, success, error,
confirm_needed. Dialogue state names (listen/think/speak/...) are aliased
onto these so the existing ``EarconPlayer`` protocol keeps working.

Rules:
- Master volume defaults small (0.25); mute toggle; quiet-hours aware —
  during quiet hours only ``error`` and ``confirm_needed`` play, at half
  volume (an unheard confirmation is a safety issue, so confirm still
  sounds, just softer).
- Playback is best-effort and never blocks: failures are logged, not raised.
- On non-Windows or headless machines playback is a no-op (NullPlayer).
"""

from __future__ import annotations

import logging
import math
import struct
import threading
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SAMPLE_RATE = 22050

# name -> list of (freq_hz, duration_ms, delay_ms)
EARCON_SCORES: Dict[str, List[Tuple[int, int, int]]] = {
    "wake": [(880, 90, 0), (1174, 110, 90)],
    "thinking_start": [(520, 70, 0), (660, 70, 70)],
    "success": [(784, 90, 0), (1046, 130, 90)],
    "error": [(220, 160, 0), (185, 200, 140)],
    "confirm_needed": [(990, 100, 0), (990, 100, 140)],
}

# Dialogue-state aliases so play("listen") etc. keep working.
ALIASES = {
    "listen": "wake",
    "think": "thinking_start",
    "thinking": "thinking_start",
    "speak": "success",
    "confirm": "confirm_needed",
    "idle": "wake",
}

URGENT = {"error", "confirm_needed"}


def _tone(freq: int, ms: int, volume: float) -> bytes:
    n = int(SAMPLE_RATE * ms / 1000)
    out = bytearray()
    for i in range(n):
        t = i / SAMPLE_RATE
        # sine with raised-cosine envelope (no clicks)
        env = math.sin(math.pi * i / n) ** 0.5
        v = int(32767 * volume * env * math.sin(2 * math.pi * freq * t))
        out += struct.pack("<h", v)
    return bytes(out)



def synth_earcon(name: str, volume: float = 0.25) -> bytes:
    """Render an earcon score to 16-bit mono PCM bytes.

    Delays in the score are absolute offsets from the start; overlapping
    tones are mixed (added with clipping).
    """
    score = EARCON_SCORES.get(name)
    if score is None:
        raise KeyError(f"unknown earcon {name!r}")
    total_ms = max(delay + ms for _, ms, delay in score)
    buf = bytearray(b"\x00\x00" * int(SAMPLE_RATE * total_ms / 1000))
    for freq, ms, delay in score:
        tone = _tone(freq, ms, volume)
        start = int(SAMPLE_RATE * delay / 1000) * 2
        for i in range(0, len(tone), 2):
            j = start + i
            if j + 2 > len(buf):
                break
            a = struct.unpack("<h", buf[j:j + 2])[0]
            b = struct.unpack("<h", tone[i:i + 2])[0]
            v = max(-32768, min(32767, a + b))
            buf[j:j + 2] = struct.pack("<h", v)
    return bytes(buf)


def write_wav(path: Path, pcm: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)


@dataclass
class EarconConfig:
    muted: bool = False
    volume: float = 0.25          # master, 0.0..1.0 (small by design)
    quiet_hours_start: str = ""   # "23:00" or ""
    quiet_hours_end: str = ""
    data_dir: Optional[Path] = None


def _in_quiet_hours(start: str, end: str, now: Optional[datetime] = None) -> bool:
    if not start or not end:
        return False
    now = now or datetime.now()
    try:
        sh, sm = map(int, start.split(":"))
        eh, em = map(int, end.split(":"))
    except ValueError:
        return False
    cur = now.hour * 60 + now.minute
    s, e = sh * 60 + sm, eh * 60 + em
    return cur >= s or cur < e if s > e else s <= cur < e


class EarconPlayer:
    """Plays the five canonical earcons. Thread-safe, never blocks."""

    def __init__(self, config: Optional[EarconConfig] = None) -> None:
        self.config = config or EarconConfig()
        self._lock = threading.Lock()
        self._cache: Dict[str, Path] = {}

    # -- public API (matches the dialogue.py EarconPlayer protocol) --------
    def play(self, name: str) -> None:
        canonical = ALIASES.get(name, name)
        if canonical not in EARCON_SCORES:
            logger.debug("unknown earcon %r ignored", name)
            return
        if self.config.muted:
            return
        quiet = _in_quiet_hours(self.config.quiet_hours_start,
                                self.config.quiet_hours_end)
        if quiet and canonical not in URGENT:
            return  # silence is the point of quiet hours
        volume = self.config.volume * (0.5 if quiet else 1.0)
        threading.Thread(target=self._play_async, args=(canonical, volume),
                         daemon=True).start()

    def set_muted(self, muted: bool) -> None:
        self.config.muted = muted

    # -- internals ----------------------------------------------------------
    def _wav_path(self, name: str, volume: float) -> Path:
        base = self.config.data_dir or (Path.home() / ".jarvis" / "earcons")
        key = f"{name}_{volume:.2f}"
        if key not in self._cache:
            pcm = synth_earcon(name, volume)
            path = base / f"{key}.wav"
            write_wav(path, pcm)
            self._cache[key] = path
        return self._cache[key]

    def _play_async(self, name: str, volume: float) -> None:
        try:
            import winsound  # Windows only
        except ImportError:
            logger.debug("earcon %r skipped (no audio backend)", name)
            return
        try:
            with self._lock:
                winsound.PlaySound(str(self._wav_path(name, volume)),
                                   winsound.SND_FILENAME)
        except Exception as e:
            logger.debug("earcon %r failed: %s", name, e)
