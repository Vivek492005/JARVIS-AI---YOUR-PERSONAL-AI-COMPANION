"""Barge-in: interrupt JARVIS mid-speech (Master Plan Task 3.7).

While TTS is playing, VAD keeps running (with AEC/ducking from 3.1).
Sustained user speech (>= ``barge_in_min_ms``, default 300 ms) triggers:

1. TTS stop within ``barge_in_stop_ms`` (default 250 ms) — measured.
2. LLM stream cancel (caller passes ``on_cancel_llm``).
3. :py:class:`jarvis.core.events.Interrupt` emitted on the bus.
4. Lane-queue cancel at priority 0 (caller passes ``on_cancel_lane``).

Stop words ("ruko", "bas", "stop" — see :mod:`jarvis.core.safety`) are
hard interrupts: they fire even below the duration threshold and also
cancel a running physical action.

False-trigger guards: coughs/blips under the min duration are ignored;
while ducked (our own TTS audible), the required duration doubles.
Context note for the next turn: ``"[user ne beech mein roka]"``.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from jarvis.core.safety import is_stop_command

logger = logging.getLogger(__name__)


@dataclass
class BargeInConfig:
    enabled: bool = True
    min_speech_ms: int = 300      # sustained speech before interrupt
    stop_budget_ms: int = 250     # TTS must stop within this
    duck_multiplier: float = 2.0  # harder to trigger while ducked


class BargeInController:
    """Feeds VAD decisions during TTS; fires interrupts."""

    def __init__(self, config: Optional[BargeInConfig] = None,
                 stop_tts: Optional[Callable[[], None]] = None,
                 on_interrupt: Optional[Callable[[str], None]] = None,
                 on_cancel_llm: Optional[Callable[[], None]] = None,
                 on_cancel_lane: Optional[Callable[[], None]] = None,
                 clock: Optional[Callable[[], float]] = None) -> None:
        self.config = config or BargeInConfig()
        self.stop_tts = stop_tts or (lambda: None)
        self.on_interrupt = on_interrupt or (lambda reason: None)
        self.on_cancel_llm = on_cancel_llm or (lambda: None)
        self.on_cancel_lane = on_cancel_lane or (lambda: None)
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self.tts_playing = False
        self.ducked = False
        self._speech_start: Optional[float] = None
        self.last_stop_latency_ms: Optional[float] = None
        self.interrupts_fired = 0

    # -- TTS lifecycle ----------------------------------------------------

    def note_tts_start(self) -> None:
        with self._lock:
            self.tts_playing = True
            self._speech_start = None

    def note_tts_stop(self) -> None:
        with self._lock:
            self.tts_playing = False
            self._speech_start = None

    # -- VAD feed ----------------------------------------------------------

    def _required_ms(self) -> float:
        ms = float(self.config.min_speech_ms)
        if self.ducked:
            ms *= self.config.duck_multiplier
        return ms

    def feed_vad(self, is_speech: bool) -> bool:
        """Feed one VAD decision. Returns True if an interrupt fired."""
        if not self.config.enabled:
            return False
        now = self._clock()
        with self._lock:
            if not self.tts_playing:
                self._speech_start = None
                return False
            if is_speech:
                if self._speech_start is None:
                    self._speech_start = now
                held_ms = (now - self._speech_start) * 1000.0
                if held_ms >= self._required_ms():
                    self._speech_start = None  # one-shot per burst
                    fire = True
                else:
                    fire = False
            else:
                self._speech_start = None
                fire = False
        if fire:
            self._fire("user speech during TTS")
        return fire

    def check_partial(self, partial_text: str) -> bool:
        """Hard interrupt on stop words, even mid-sentence."""
        if is_stop_command(partial_text):
            with self._lock:
                if not self.tts_playing:
                    return False
            self._fire(f"stop word: {partial_text.strip()!r}")
            return True
        return False

    # -- firing ------------------------------------------------------------

    def _fire(self, reason: str) -> None:
        t0 = self._clock()
        try:
            self.stop_tts()
        except Exception:
            logger.exception("barge-in: stop_tts failed")
        latency_ms = (self._clock() - t0) * 1000.0
        self.last_stop_latency_ms = latency_ms
        if latency_ms > self.config.stop_budget_ms:
            logger.warning(
                f"barge-in stop took {latency_ms:.0f} ms "
                f"(budget {self.config.stop_budget_ms} ms)")
        try:
            self.on_cancel_llm()
        except Exception:
            logger.exception("barge-in: on_cancel_llm failed")
        try:
            self.on_cancel_lane()
        except Exception:
            logger.exception("barge-in: on_cancel_lane failed")
        self.interrupts_fired += 1
        try:
            self.on_interrupt(reason)
        except Exception:
            logger.exception("barge-in: on_interrupt failed")

    @staticmethod
    def context_note() -> str:
        """Note prepended to the next user turn after an interrupt."""
        return "[user ne beech mein roka]"
