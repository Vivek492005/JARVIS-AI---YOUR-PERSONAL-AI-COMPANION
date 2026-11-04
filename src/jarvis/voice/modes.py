"""Input modes (Master Plan Task 3.9).

- ``wakeword`` — mic always listening for the wake word (default; F-07
  fix keeps this gated by require_wake_word).
- ``ptt`` — push-to-talk: mic captures only while the hotkey is held.
- ``typed`` — mic off; text input only.
- ``quiet`` — whisper-level: mic on, but replies are text-only
  (no TTS). For meetings / night use.
- ``quiet_hours`` — schedule (``quiet_hours_start/end`` "HH:MM"): the mic
  auto-disables during the window, re-enables after.

Mode switches come from HUD/tray/voice; every switch emits a bus event.
"""

from __future__ import annotations

import datetime
import logging
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class InputMode(Enum):
    WAKEWORD = "wakeword"
    PTT = "ptt"
    TYPED = "typed"
    QUIET = "quiet"


@dataclass
class QuietHours:
    start: str = ""  # "HH:MM"
    end: str = ""  # "HH:MM"

    def enabled(self) -> bool:
        return bool(self.start and self.end)

    def active(self, now: Optional[datetime.time] = None) -> bool:
        """True if ``now`` falls inside the quiet window."""
        if not self.enabled():
            return False
        now = now or datetime.datetime.now().time()
        s = datetime.time(*map(int, self.start.split(":")))
        e = datetime.time(*map(int, self.end.split(":")))
        if s <= e:
            return s <= now < e
        return now >= s or now < e  # overnight window


class InputModeManager:
    """Owns the current input mode + quiet-hours automation."""

    def __init__(
        self,
        initial: InputMode = InputMode.WAKEWORD,
        quiet_hours: Optional[QuietHours] = None,
        on_change: Optional[Callable[[InputMode, str], None]] = None,
    ) -> None:
        self._mode = initial
        self.quiet_hours = quiet_hours or QuietHours()
        self._on_change = on_change or (lambda mode, reason: None)
        self._lock = threading.Lock()
        self._quiet_override = False  # True while quiet-hours force mic off

    @property
    def mode(self) -> InputMode:
        with self._lock:
            return self._mode

    def set_mode(self, mode: InputMode, reason: str = "user") -> InputMode:
        with self._lock:
            old = self._mode
            self._mode = mode
        if old != mode:
            logger.info(f"input mode {old.value} -> {mode.value} ({reason})")
            try:
                self._on_change(mode, reason)
            except Exception:
                logger.exception("input mode on_change failed")
        return mode

    # -- derived capture policy -------------------------------------------

    def mic_captures(self, now: Optional[datetime.time] = None) -> bool:
        """Should the mic capture audio right now?"""
        if self.quiet_hours.active(now):
            return False
        return self._mode in (InputMode.WAKEWORD, InputMode.PTT, InputMode.QUIET)

    def tts_allowed(self) -> bool:
        """Quiet mode: replies are text-only."""
        return self._mode != InputMode.QUIET

    def requires_wake_word(self) -> bool:
        return self._mode == InputMode.WAKEWORD

    def ptt_armed(self) -> bool:
        return self._mode == InputMode.PTT

    def tick_quiet_hours(self, now: Optional[datetime.time] = None) -> bool:
        """Call periodically; returns True if quiet-hours state changed."""
        active = self.quiet_hours.active(now)
        with self._lock:
            changed = active != self._quiet_override
            self._quiet_override = active
        if changed:
            logger.info(
                f"quiet hours {'started' if active else 'ended'}: mic {'off' if active else 'on'}"
            )
        return changed
