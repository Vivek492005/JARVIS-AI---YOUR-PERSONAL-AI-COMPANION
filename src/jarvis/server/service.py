"""jarvisd service (Master Plan Task 2.4): the headless core.

:class:`JarvisService` owns the event bus, the lane queue and the command
handler. UIs (tkinter, CLI, HTTP/WS) are thin clients over it — they never
touch the brain directly.
"""

from __future__ import annotations

import logging
import threading
from time import time
from typing import Callable, Optional

from jarvis.core.events import UtteranceFinal, get_bus, new_trace
from jarvis.core.lanes import CancelToken, LaneQueue, Priority

logger = logging.getLogger(__name__)

# handler(text, token, service) -> str
CommandHandler = Callable[[str, CancelToken, "JarvisService"], str]


class JarvisService:
    """In-process jarvisd core. Transport-agnostic; see server.api."""

    def __init__(self, bus=None, handler: Optional[CommandHandler] = None,
                 flush_on_interrupt: bool = True) -> None:
        self.bus = bus or get_bus()
        self.lanes = LaneQueue(bus=self.bus, flush_on_interrupt=flush_on_interrupt)
        self.handler: CommandHandler = handler or self._agent_handler
        self.started_at: Optional[float] = None
        self.commands_processed = 0
        self.last_error: Optional[str] = None
        self._agent = None
        self._router = None
        self._lock = threading.Lock()

    # -- lifecycle -----------------------------------------------------
    def start(self) -> None:
        self.lanes.start()
        self.started_at = time()
        logger.info("jarvisd service started")

    def stop(self) -> None:
        self.lanes.stop()
        logger.info("jarvisd service stopped")

    @property
    def running(self) -> bool:
        return self.lanes.running

    # -- commands ------------------------------------------------------
    def submit_command(self, text: str,
                       priority: Priority = Priority.TASK) -> CancelToken:
        """Enqueue a command; returns its CancelToken."""
        if not text or not text.strip():
            raise ValueError("empty command")
        return self.lanes.submit(
            lambda token: self._run_command(text.strip(), token),
            priority=priority, name=text.strip()[:40])

    def _run_command(self, text: str, token: CancelToken) -> str:
        trace = new_trace()
        self.bus.emit(UtteranceFinal(trace=trace, text=text))
        try:
            result = self.handler(text, token, self)
        except Exception as e:  # noqa: BLE001 - never wedge the lane
            logger.exception("command handler crashed")
            self.last_error = str(e)
            result = f"Sorry, that command failed: {e}"
        with self._lock:
            self.commands_processed += 1
        return result

    def interrupt(self, reason: str = "") -> None:
        self.lanes.interrupt(reason=reason)

    def on_interrupt(self, fn: Callable[[], None]):
        return self.lanes.on_interrupt(fn)

    # -- state / events ------------------------------------------------
    def get_state(self) -> dict:
        from jarvis import __version__
        uptime = (time() - self.started_at) if self.started_at else 0.0
        return {
            "v": 1,
            "running": self.running,
            "version": __version__,
            "uptime_s": round(uptime, 1),
            "queue_depth": self.lanes.qsize(),
            "commands_processed": self.commands_processed,
            "last_error": self.last_error,
        }

    def on_event(self, etype, fn):
        """Subscribe to bus events (client use)."""
        return self.bus.on(etype, fn)

    # -- default brain -------------------------------------------------
    def _get_agent(self):
        # Lazy: constructing the agent reads settings/secrets.
        if self._agent is None:
            from jarvis.brain.agent import AIAgent
            self._agent = AIAgent(bus=self.bus)
        return self._agent

    def _agent_handler(self, text: str, token: CancelToken,
                       service: "JarvisService") -> str:
        """Default handler: reflex router (System-1) + LLM agent (System-2).

        Built lazily so a service that never receives a command never pays
        for the imports; reflex-only turns never initialize the LLM
        providers at all.
        """
        if self._router is None:
            from jarvis.brain.router import Router
            self._router = Router()
        return self._router.handle(text)
