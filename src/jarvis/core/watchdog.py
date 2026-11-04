"""Service watchdog (Task 8.3).

Supervises the jarvisd child process: restarts it on crash with exponential
backoff, gives up after N consecutive failures, and records every crash via
:mod:`jarvis.core.crash`.

This is intentionally small: the OS (Task Scheduler / autostart) owns
boot-time launch; the watchdog owns *runtime* resilience.
"""

from __future__ import annotations

import logging
import subprocess  # noqa: S404 — fixed argv, spawned by the user, not a shell
import time
from dataclasses import dataclass, field
from typing import List, Optional

from jarvis.core.crash import write_crash_report

logger = logging.getLogger(__name__)


@dataclass
class WatchdogConfig:
    command: List[str]  # e.g. [sys.executable, "-m", "jarvis", "serve"]
    max_restarts: int = 5  # give up after this many crashes...
    window_s: float = 300.0  # ...inside this window
    backoff_base_s: float = 2.0  # first restart waits this long
    backoff_max_s: float = 60.0  # cap the wait
    restart_timestamps: List[float] = field(default_factory=list)


class Watchdog:
    """Run `command`, restart it when it exits non-zero."""

    def __init__(self, config: WatchdogConfig) -> None:
        self.cfg = config
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def _prune_window(self, now: float) -> None:
        cutoff = now - self.cfg.window_s
        self.cfg.restart_timestamps = [t for t in self.cfg.restart_timestamps if t >= cutoff]

    def _backoff(self, attempt: int) -> float:
        return min(self.cfg.backoff_base_s * (2**attempt), self.cfg.backoff_max_s)

    def run_once(self) -> int:
        """Spawn the child once, wait for it, return its exit code.

        Separated from :meth:`supervise` so tests can drive single cycles.
        """
        proc = subprocess.Popen(self.cfg.command)  # noqa: S603 — fixed argv
        try:
            return proc.wait()
        finally:
            # Reap defensively; a crashed child must not linger as a zombie.
            try:
                proc.kill()
            except Exception:  # noqa: S110 — already exited
                pass

    def supervise(self) -> int:
        """Loop until the child exits 0, stop() is called, or we give up.

        Returns 0 on clean exit / stop, 1 when the restart budget is spent.
        """
        attempt = 0
        while not self._stop:
            code = self.run_once()
            if code == 0:
                logger.info("watchdog: child exited cleanly")
                return 0
            now = time.time()
            self._prune_window(now)
            self.cfg.restart_timestamps.append(now)
            write_crash_report(
                summary=f"jarvisd exited with code {code}",
                context={"command": self.cfg.command, "attempt": attempt},
            )
            if len(self.cfg.restart_timestamps) > self.cfg.max_restarts:
                logger.error(
                    "watchdog: %d crashes in %.0fs — giving up",
                    len(self.cfg.restart_timestamps),
                    self.cfg.window_s,
                )
                return 1
            wait = self._backoff(attempt)
            logger.warning("watchdog: restarting in %.1fs (attempt %d)", wait, attempt + 1)
            time.sleep(wait)
            attempt += 1
        logger.info("watchdog: stopped by request")
        return 0


def supervise_jarvisd(argv: Optional[List[str]] = None) -> int:
    """Entry point used by the Windows Task Scheduler / autostart shortcut."""
    import sys

    cmd = [sys.executable, "-m", "jarvis", "serve", *(argv or [])]
    return Watchdog(WatchdogConfig(command=cmd)).supervise()
