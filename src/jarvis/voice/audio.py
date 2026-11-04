"""Audio capture (Master Plan Task 3.1).

16 kHz mono capture in 20-30 ms frames, with a ring buffer that always
keeps the last ``preroll_s`` seconds of audio so the first syllable of an
utterance is never cut.

Echo handling (the mic hears JARVIS's own speakers) is a strategy ladder,
cheapest first:
  1. ``headset`` — user wears a headset; nothing to do in software.
  2. ``ducking`` (default) — while TTS is playing, the wake-word detector
     raises its threshold / pauses, so our own voice can't retrigger us.
  3. ``webrtc`` — real acoustic echo cancellation via WebRTC APM or
     speexdsp bindings. Heavy native dependency; interface is here, the
     backend is loaded lazily and documented in docs/AUDIO_SETUP.md.

Noise suppression is an optional flag; the plan says to measure WER
before/after and only keep it if it helps (see evals/stt/).

``sounddevice`` is imported lazily so the base install stays light and
headless CI never touches audio hardware.
"""

from __future__ import annotations

import collections
import logging
import queue
import threading
from dataclasses import dataclass, field
from typing import Callable, Deque, List, Optional, Protocol

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # 16-bit PCM
CHANNELS = 1


class AudioSource(Protocol):
    """Anything that yields 16-bit mono PCM frames."""

    @property
    def sample_rate(self) -> int: ...

    def read_frame(self) -> Optional[bytes]:
        """Next frame, or None at end-of-stream."""
        ...

    def close(self) -> None: ...


class RingBuffer:
    """Thread-safe ring buffer holding the last ``capacity_s`` of audio.

    ``drain_preroll()`` returns everything buffered so far — call it the
    moment VAD fires so the utterance starts *before* the trigger frame.
    """

    def __init__(
        self, sample_rate: int = SAMPLE_RATE, capacity_s: float = 1.5, frame_ms: int = 20
    ) -> None:
        self.frame_bytes = int(sample_rate * SAMPLE_WIDTH * CHANNELS * frame_ms / 1000)
        max_frames = max(1, int(capacity_s * 1000 / frame_ms))
        self._buf: Deque[bytes] = collections.deque(maxlen=max_frames)
        self._lock = threading.Lock()

    def push(self, frame: bytes) -> None:
        with self._lock:
            self._buf.append(frame)

    def drain_preroll(self) -> bytes:
        """Return and clear all buffered audio (oldest first)."""
        with self._lock:
            data = b"".join(self._buf)
            self._buf.clear()
        return data

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)


@dataclass
class AudioDevice:
    index: int
    name: str
    max_input_channels: int = 1
    default_samplerate: float = SAMPLE_RATE


def list_input_devices() -> List[AudioDevice]:
    """List input devices. Returns [] when sounddevice is unavailable."""
    try:
        import sounddevice as sd
    except ImportError:
        logger.debug("sounddevice not installed; no audio devices listed")
        return []
    devices: List[AudioDevice] = []
    try:
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_input_channels", 0) > 0:
                devices.append(
                    AudioDevice(
                        index=i,
                        name=str(d.get("name", f"device-{i}")),
                        max_input_channels=int(d["max_input_channels"]),
                        default_samplerate=float(d.get("default_samplerate", SAMPLE_RATE)),
                    )
                )
    except Exception as e:  # PortAudio missing etc.
        logger.warning(f"Could not query audio devices: {e}")
    return devices


class SoundDeviceSource:
    """Live mic via sounddevice. Lazy import; raises RuntimeError if missing."""

    def __init__(
        self, device: Optional[int] = None, sample_rate: int = SAMPLE_RATE, frame_ms: int = 20
    ) -> None:
        try:
            import sounddevice as sd
        except ImportError as e:
            raise RuntimeError(
                "sounddevice is not installed. Install it with "
                "`pip install jarvis-assistant[audio]` (see docs/AUDIO_SETUP.md)."
            ) from e
        self._sd = sd
        self._sample_rate = sample_rate
        self.frame_bytes = int(sample_rate * SAMPLE_WIDTH * CHANNELS * frame_ms / 1000)
        self._frames: "queue.Queue[Optional[bytes]]" = queue.Queue(maxsize=200)
        self._stream = sd.InputStream(
            device=device,
            channels=CHANNELS,
            samplerate=sample_rate,
            dtype="int16",
            blocksize=self.frame_bytes // 2,
            callback=self._callback,
        )

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001,ANN202
        if status:
            logger.debug(f"audio callback status: {status}")
        try:
            self._frames.put_nowait(bytes(indata))
        except queue.Full:
            pass  # drop oldest implicitly by skipping; capture keeps up

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def start(self) -> None:
        self._stream.start()

    def read_frame(self) -> Optional[bytes]:
        try:
            return self._frames.get(timeout=1.0)
        except queue.Empty:
            return None

    def close(self) -> None:
        try:
            self._stream.stop()
            self._stream.close()
        except Exception as e:
            logger.debug(f"audio source close failed: {e}")


class EchoGuard:
    """Coordinates echo policy between TTS playback and the mic pipeline.

    Modes (config ``voice.aec_mode``):
      - ``headset``: user promises a headset; no software action.
      - ``ducking`` (default): while ``tts_active`` is True, wake-word
        sensitivity is raised (implemented by the wake-word engine reading
        :meth:`ducked`) and VAD-gated barge-in requires a longer minimum
        speech duration.
      - ``webrtc``: placeholder for a real AEC backend (WebRTC APM /
        speexdsp). Raises a clear error until a backend registers via
        :meth:`register_aec_backend`.
    """

    def __init__(self, mode: str = "ducking") -> None:
        if mode not in ("headset", "ducking", "webrtc"):
            raise ValueError(f"unknown aec_mode: {mode!r}")
        self.mode = mode
        self.tts_active = False
        self._aec_backend: Optional[Callable[[bytes, bytes], bytes]] = None

    def register_aec_backend(self, fn: Callable[[bytes, bytes], bytes]) -> None:
        """Register ``fn(mic_frame, reference_frame) -> clean_frame``."""
        self._aec_backend = fn

    @property
    def ducked(self) -> bool:
        """True while our own TTS should suppress mic triggers."""
        return self.mode == "ducking" and self.tts_active

    def process(self, mic_frame: bytes, reference_frame: bytes = b"") -> bytes:
        """Apply AEC if a backend is registered; else pass through."""
        if self.mode == "webrtc":
            if self._aec_backend is None:
                raise RuntimeError(
                    "aec_mode='webrtc' but no AEC backend registered. "
                    "See docs/AUDIO_SETUP.md for speexdsp/WebRTC options."
                )
            return self._aec_backend(mic_frame, reference_frame)
        return mic_frame


class AudioCapture:
    """High-level capture: source + pre-roll ring buffer + echo guard.

    Usage:
        cap = AudioCapture(source=FakeMic(...))   # or SoundDeviceSource()
        cap.start()
        for frame in cap.frames():  # blocks; None ends the stream
            ...
        cap.stop()
    """

    def __init__(
        self,
        source: AudioSource,
        frame_ms: int = 20,
        preroll_s: float = 1.5,
        echo_guard: Optional[EchoGuard] = None,
        on_frame: Optional[Callable[[bytes], None]] = None,
    ) -> None:
        self.source = source
        self.ring = RingBuffer(source.sample_rate, preroll_s, frame_ms)
        self.echo_guard = echo_guard or EchoGuard()
        self.on_frame = on_frame
        self._running = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if hasattr(self.source, "start"):
            self.source.start()  # type: ignore[attr-defined]
        self._running.set()
        self._thread = threading.Thread(target=self._pump, daemon=True, name="audio-capture")
        self._thread.start()

    def _pump(self) -> None:
        while self._running.is_set():
            frame = self.source.read_frame()
            if frame is None:
                break
            frame = self.echo_guard.process(frame)
            self.ring.push(frame)
            if self.on_frame:
                try:
                    self.on_frame(frame)
                except Exception:
                    logger.exception("on_frame callback failed")

    def stop(self) -> None:
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=2.0)
        self.source.close()

    def drain_preroll(self) -> bytes:
        """Audio from the last ``preroll_s`` — call when VAD/wake fires."""
        return self.ring.drain_preroll()


# ---------------------------------------------------------------------------
# jarvis doctor integration
# ---------------------------------------------------------------------------


@dataclass
class AudioCheck:
    ok: bool
    detail: str
    devices: List[AudioDevice] = field(default_factory=list)


def check_audio() -> AudioCheck:
    """Used by ``jarvis doctor``: is capture even possible here?"""
    devices = list_input_devices()
    try:
        import sounddevice  # noqa: F401

        has_sd = True
    except ImportError:
        has_sd = False
    if not has_sd:
        return AudioCheck(False, "sounddevice not installed (pip install jarvis-assistant[audio])")
    if not devices:
        return AudioCheck(False, "sounddevice installed but no input devices found")
    return AudioCheck(True, f"{len(devices)} input device(s) available", devices)
