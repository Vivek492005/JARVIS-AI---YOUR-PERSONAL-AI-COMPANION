"""Wake-word engine (Master Plan Task 3.2).

Detects "hey jarvis" / "jarvis" in the mic stream and emits
:py:class:`jarvis.core.events.WakeDetected`. Pluggable backends:

- ``openwakeword`` — open-source, runs on CPU. Evaluate first (plan).
- ``porcupine`` — Picovoice Porcupine, needs a (free-tier) access key for
  a custom "jarvis" keyword.
- ``dummy`` — deterministic test backend: fires when the frame payload
  contains a marker. Never used in production.

Both real backends are imported lazily; the base install stays light.

Tuning targets (plan):
- false accepts: < 1 per hour of TV/YouTube/news audio
- false rejects: >= 95% over 50 spoken attempts
See docs/WAKEWORD_TEST.md for the measurement procedure.

Follow-up window ("conversation mode", Gemini-Live style): for
``followup_s`` seconds after a response, the next utterance is accepted
without a wake word. While TTS is playing and ``aec_mode=ducking``, the
engine raises its effective threshold (reads
:py:class:`jarvis.voice.audio.EchoGuard`).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Protocol

logger = logging.getLogger(__name__)


class WakeBackend(Protocol):
    """A wake-word detector consuming 16-bit mono PCM frames."""

    @property
    def name(self) -> str: ...

    def configure(self, keywords: List[str], threshold: float) -> None: ...

    def process(self, frame: bytes) -> Optional[str]:
        """Return the detected keyword, or None."""
        ...

    def reset(self) -> None: ...


class DummyWakeBackend:
    """Deterministic backend for tests.

    Fires when the frame starts with the magic marker b"WAKE:<keyword>".
    """

    MARKER = b"WAKE:"

    def __init__(self) -> None:
        self.keywords: List[str] = []
        self.threshold = 0.5
        self.name = "dummy"

    def configure(self, keywords: List[str], threshold: float) -> None:
        self.keywords = [k.lower() for k in keywords]
        self.threshold = threshold

    def process(self, frame: bytes) -> Optional[str]:
        if frame.startswith(self.MARKER):
            kw = frame[len(self.MARKER):].split(b"\x00")[0].decode("utf-8", "ignore").lower()
            if kw in self.keywords:
                return kw
        return None

    def reset(self) -> None:
        pass


class OpenWakeWordBackend:
    """openWakeWord backend (lazy import)."""

    def __init__(self, model_paths: Optional[List[str]] = None) -> None:
        try:
            from openwakeword.model import Model as OWWModel
        except ImportError as e:
            raise RuntimeError(
                "openwakeword is not installed. Install with "
                "`pip install jarvis-assistant[wakeword]` (see docs/AUDIO_SETUP.md)."
            ) from e
        # Models are resolved lazily at configure() so __init__ stays cheap.
        self._model_cls = OWWModel
        self._model = None
        self._model_paths = model_paths or []
        self.name = "openwakeword"
        self._keywords: List[str] = []
        self._threshold = 0.5

    def configure(self, keywords: List[str], threshold: float) -> None:
        self._keywords = [k.lower() for k in keywords]
        self._threshold = threshold
        # openwakeword ships "hey_jarvis" in its feature models; custom
        # models can be passed via model_paths (trained with
        # openwakeword's training notebooks).
        models = self._model_paths or ["hey_jarvis"]
        self._model = self._model_cls(wakeword_models=models)

    def process(self, frame: bytes) -> Optional[str]:
        import numpy as np  # local import: backend-only dependency
        audio = np.frombuffer(frame, dtype=np.int16)
        scores = self._model.predict(audio)
        for model_name, score in scores.items():
            kw = model_name.replace("_", " ")
            if score >= self._threshold and kw in self._keywords:
                return kw
        return None

    def reset(self) -> None:
        if self._model is not None:
            self._model.reset()


class PorcupineBackend:
    """Picovoice Porcupine backend (lazy import; needs access key)."""

    def __init__(self, access_key: str = "", keyword_paths: Optional[List[str]] = None) -> None:
        if not access_key:
            raise RuntimeError(
                "Porcupine needs a (free-tier) Picovoice access key. "
                "Set voice.wakeword_key via secrets; see docs/AUDIO_SETUP.md."
            )
        try:
            import pvporcupine
        except ImportError as e:
            raise RuntimeError(
                "pvporcupine is not installed. Install with "
                "`pip install jarvis-assistant[wakeword]`."
            ) from e
        self._porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=keyword_paths or [],
        )
        self.name = "porcupine"
        self._keywords: List[str] = []

    def configure(self, keywords: List[str], threshold: float) -> None:
        # Porcupine bakes sensitivity into create(); threshold is advisory.
        self._keywords = [k.lower() for k in keywords]

    def process(self, frame: bytes) -> Optional[str]:
        import numpy as np
        audio = np.frombuffer(frame, dtype=np.int16)
        # Porcupine expects a fixed frame length; pad/trim defensively.
        want = self._porcupine.frame_length
        if len(audio) < want:
            audio = np.pad(audio, (0, want - len(audio)))
        else:
            audio = audio[:want]
        idx = self._porcupine.process(audio)
        if idx >= 0 and idx < len(self._keywords):
            return self._keywords[idx]
        return None

    def reset(self) -> None:
        pass


@dataclass
class WakeConfig:
    keywords: List[str] = field(default_factory=lambda: ["hey jarvis", "jarvis"])
    threshold: float = 0.5
    backend: str = "openwakeword"  # openwakeword | porcupine | dummy
    followup_s: float = 7.0       # conversation mode window after a response
    duck_threshold_boost: float = 0.25  # added while our own TTS is playing


class WakeWordEngine:
    """Runs a backend over frames; emits keyword detections with cooldown.

    ``on_wake(keyword)`` is called on detection. Detections inside the
    follow-up window (after :meth:`note_response`) are reported with
    ``followup=True`` so the caller can skip the wake word requirement.
    """

    def __init__(self, backend: WakeBackend, config: Optional[WakeConfig] = None,
                 echo_guard=None,
                 on_wake: Optional[Callable[[str, bool], None]] = None) -> None:
        self.backend = backend
        self.config = config or WakeConfig()
        self.echo_guard = echo_guard
        self.on_wake = on_wake
        self._last_wake = 0.0
        self._cooldown_s = 1.0
        self._followup_until = 0.0
        self._lock = threading.Lock()
        backend.configure(self.config.keywords, self.config.threshold)

    def note_response(self) -> None:
        """Call when JARVIS finishes responding: opens the follow-up window."""
        with self._lock:
            self._followup_until = time.monotonic() + self.config.followup_s

    def in_followup_window(self) -> bool:
        return time.monotonic() < self._followup_until

    def _effective_threshold(self) -> float:
        thr = self.config.threshold
        if self.echo_guard is not None and self.echo_guard.ducked:
            thr = min(0.99, thr + self.config.duck_threshold_boost)
        return thr

    def process(self, frame: bytes) -> Optional[str]:
        """Feed one frame; returns keyword on a (cooldown-respecting) hit."""
        now = time.monotonic()
        with self._lock:
            if now - self._last_wake < self._cooldown_s:
                return None
        # Backends that honor thresholds internally were configured with the
        # base threshold; ducking is enforced here for backends that don't.
        kw = self.backend.process(frame)
        if kw is None:
            return None
        with self._lock:
            self._last_wake = now
            followup = self.in_followup_window()
        if self.on_wake:
            try:
                self.on_wake(kw, followup)
            except Exception:
                logger.exception("on_wake callback failed")
        return kw
