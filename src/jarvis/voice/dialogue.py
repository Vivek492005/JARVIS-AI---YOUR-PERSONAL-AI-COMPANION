"""Dialogue state machine + earcons (Master Plan Task 3.8).

States: IDLE -> LISTENING -> THINKING -> SPEAKING -> CONFIRMING -> IDLE.
Every transition emits a bus event; each state has a short earcon
(a few-hundred-ms blip) played through an :py:class:`EarconPlayer`.

Earcon backends:
- ``NullEarconPlayer`` — silent (tests, headless).
- ``WinsoundEarconPlayer`` — Windows ``winsound.Beep`` (lazy).
- ``WavEarconPlayer`` — plays bundled WAVs via the TTS audio path.

"Thinking" filler ("ek second…") is only spoken when the think phase
exceeds 1.2 s — otherwise it would just add latency theater.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

THINK_FILLER_LATENCY_S = 1.2


class DialogueState(Enum):
    IDLE = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()
    CONFIRMING = auto()


# Legal transitions (plus any -> IDLE on error/cancel).
_TRANSITIONS: Dict[DialogueState, List[DialogueState]] = {
    DialogueState.IDLE: [DialogueState.LISTENING],
    DialogueState.LISTENING: [DialogueState.THINKING, DialogueState.IDLE],
    DialogueState.THINKING: [DialogueState.SPEAKING, DialogueState.CONFIRMING,
                             DialogueState.IDLE],
    DialogueState.SPEAKING: [DialogueState.IDLE, DialogueState.LISTENING],
    DialogueState.CONFIRMING: [DialogueState.THINKING, DialogueState.IDLE],
}


class EarconPlayer:
    """Plays short UI sounds. ``play(name)`` never raises."""

    def play(self, name: str) -> None: ...


class NullEarconPlayer(EarconPlayer):
    def __init__(self) -> None:
        self.played: List[str] = []

    def play(self, name: str) -> None:
        self.played.append(name)


class WinsoundEarconPlayer(EarconPlayer):
    """Windows beeps; frequency/duration per earcon name."""

    _TONES = {
        "wake": (880, 120),
        "listen": (660, 80),
        "think": (520, 80),
        "speak": (740, 80),
        "confirm": (990, 150),
        "error": (220, 200),
        "idle": (440, 60),
    }

    def play(self, name: str) -> None:
        try:
            import winsound
            freq, dur = self._Tones.get(name, (440, 80))
            winsound.Beep(freq, dur)
        except Exception as e:
            logger.debug(f"earcon {name!r} failed: {e}")


@dataclass
class Transition:
    frm: DialogueState
    to: DialogueState
    at: float


class DialogueMachine:
    """The conversation state machine.

    ``bus_emit(event)`` publishes transitions; ``speak_filler`` is called
    with the filler text when THINKING runs long.
    """

    def __init__(self,
                 earcons: Optional[EarconPlayer] = None,
                 bus_emit: Optional[Callable] = None,
                 speak_filler: Optional[Callable[[str], None]] = None,
                 clock: Optional[Callable[[], float]] = None) -> None:
        self.state = DialogueState.IDLE
        self.earcons = earcons or NullEarconPlayer()
        self._emit = bus_emit or (lambda e: None)
        self._speak_filler = speak_filler or (lambda t: None)
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self.history: List[Transition] = []
        self._think_started: Optional[float] = None
        self._filler_spoken = False

    def to(self, state: DialogueState) -> bool:
        """Transition; returns False on illegal transitions (stays put)."""
        with self._lock:
            if state != DialogueState.IDLE and state not in _TRANSITIONS[self.state]:
                logger.warning(f"illegal dialogue transition {self.state} -> {state}")
                return False
            frm = self.state
            self.state = state
            self.history.append(Transition(frm, state, self._clock()))
            if state == DialogueState.THINKING:
                self._think_started = self._clock()
                self._filler_spoken = False
        self.earcons.play(state.name.lower())
        try:
            from jarvis.core.events import StatusChanged
            self._emit(StatusChanged(status=f"dialogue:{state.name}"))
        except Exception:
            logger.exception("dialogue bus emit failed")
        return True

    def maybe_filler(self) -> bool:
        """Speak the thinking filler if THINKING is running long."""
        with self._lock:
            if (self.state != DialogueState.THINKING or self._filler_spoken
                    or self._think_started is None):
                return False
            elapsed = self._clock() - self._think_started
            if elapsed < THINK_FILLER_LATENCY_S:
                return False
            self._filler_spoken = True
        try:
            self._speak_filler("ek second…")
        except Exception:
            logger.exception("filler speak failed")
        return True

    def reset(self) -> None:
        with self._lock:
            self.state = DialogueState.IDLE
            self.history.clear()
            self._think_started = None
            self._filler_spoken = False
