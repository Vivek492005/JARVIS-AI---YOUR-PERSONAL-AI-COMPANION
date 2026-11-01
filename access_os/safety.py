"""Task 1.8: kill switch, rate limiter, circuit breaker, stop words.

All four are the last line of defense when the policy engine, the gates,
and the user all miss something.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Callable, Deque, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Kill switch: Ctrl+Alt+Shift+J
# ---------------------------------------------------------------------------

class KillSwitch:
    """Global emergency stop.

    The switch is a threading.Event plus callbacks, so it works on every
    platform. install_hotkey() best-effort binds Ctrl+Alt+Shift+J through
    the `keyboard` package on Windows; when that is unavailable the GUI
    close button and the CLI can still trigger() it.
    """

    HOTKEY = "ctrl+alt+shift+j"

    def __init__(self):
        self._event = threading.Event()
        self._callbacks: List[Callable[[], None]] = []
        self._hotkey_handle = None

    def on_trigger(self, cb: Callable[[], None]) -> None:
        self._callbacks.append(cb)

    def trigger(self, reason: str = "kill switch") -> None:
        if self._event.is_set():
            return
        logger.warning(f"KILL SWITCH triggered ({reason})")
        self._event.set()
        for cb in self._callbacks:
            try:
                cb()
            except Exception:
                logger.exception("kill-switch callback failed")

    def is_triggered(self) -> bool:
        return self._event.is_set()

    def reset(self) -> None:
        self._event.clear()

    def install_hotkey(self) -> bool:
        """Bind Ctrl+Alt+Shift+J globally. False when unavailable."""
        try:
            import keyboard  # type: ignore
        except ImportError:
            logger.info("kill-switch hotkey unavailable: "
                        "'keyboard' package not installed")
            return False
        try:
            self._hotkey_handle = keyboard.add_hotkey(
                self.HOTKEY, lambda: self.trigger("hotkey"))
            logger.info(f"kill-switch hotkey installed: {self.HOTKEY}")
            return True
        except Exception as e:
            logger.warning(f"kill-switch hotkey install failed: {e}")
            return False

    def uninstall_hotkey(self) -> None:
        if self._hotkey_handle is None:
            return
        try:
            import keyboard  # type: ignore
            keyboard.remove_hotkey(self._hotkey_handle)
        except Exception:
            pass
        self._hotkey_handle = None


# ---------------------------------------------------------------------------
# Rate limiter: sliding window over tool calls
# ---------------------------------------------------------------------------

class RateLimiter:
    """Sliding-window rate limiter for tool calls.

    When the budget is exhausted, over_budget() is True and the caller is
    expected to set agent.rate_limited = True (the policy engine then
    DENYs non-READ calls until the window slides).
    """

    def __init__(self, max_calls: int, window_s: float = 60.0):
        self.max_calls = max_calls
        self.window_s = window_s
        self._hits: Deque[float] = deque()
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_s
        while self._hits and self._hits[0] <= cutoff:
            self._hits.popleft()

    def allow(self) -> bool:
        """Record one call. True if within budget."""
        now = time.time()
        with self._lock:
            self._prune(now)
            if len(self._hits) >= self.max_calls:
                return False
            self._hits.append(now)
            return True

    def over_budget(self) -> bool:
        now = time.time()
        with self._lock:
            self._prune(now)
            return len(self._hits) >= self.max_calls

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# ---------------------------------------------------------------------------
# Circuit breaker: consecutive tool failures
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Trips OPEN after max_failures consecutive failures; half-opens after
    cooldown_s so one probe can close it again."""

    CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"

    def __init__(self, max_failures: int = 5, cooldown_s: float = 60.0):
        self.max_failures = max_failures
        self.cooldown_s = cooldown_s
        self._failures = 0
        self._state = self.CLOSED
        self._opened_at: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == self.OPEN and self._opened_at is not None:
                if time.time() - self._opened_at >= self.cooldown_s:
                    self._state = self.HALF_OPEN
            return self._state

    def allow(self) -> bool:
        return self.state != self.OPEN

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = self.CLOSED
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.max_failures:
                if self._state != self.OPEN:
                    logger.warning(
                        f"circuit breaker OPEN after {self._failures} "
                        f"consecutive failures")
                self._state = self.OPEN
                self._opened_at = time.time()


# ---------------------------------------------------------------------------
# Spoken stop words
# ---------------------------------------------------------------------------

# Said mid-action, these stop the current TTS + skip tool dispatch.
# Kept as whole-phrase matches on the lowercased transcript.
STOP_WORDS = frozenset({
    "stop", "ruko", "ruk jao", "rukjo", "bas", "bas karo", "enough",
    "cancel", "cancel karo", "chup", "quiet", "shut up",
})


def is_stop_command(text: str) -> bool:
    t = (text or "").lower().strip().rstrip(".!")
    return t in STOP_WORDS
