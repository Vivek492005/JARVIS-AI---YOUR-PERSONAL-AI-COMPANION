"""Lane queue (Master Plan Task 2.2→2.3): serial, prioritized command execution.

One session = one lane. Tasks run strictly serially (never two pyautogui
streams at once), ordered by priority:

    INTERRUPT (0) > CONFIRM (1) > TASK (2) > BACKGROUND (3)

Threading-based (the app is threading-based; an asyncio variant would need
a dedicated loop thread for no functional gain here). Each item carries a
:class:`CancelToken`; :meth:`LaneQueue.interrupt` cancels the running item,
fires interrupt hooks (e.g. TTS stop), and — configurably — flushes queued
TASK/BACKGROUND work while keeping INTERRUPT/CONFIRM items.
"""

from __future__ import annotations

import itertools
import logging
import queue
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from time import time
from typing import Any, Callable, List, Optional

from jarvis.core.errors import LaneCancelled
from jarvis.core.events import Error, Interrupt, get_bus

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    INTERRUPT = 0
    CONFIRM = 1
    TASK = 2
    BACKGROUND = 3


class CancelToken:
    """Cooperative cancellation flag handed to every lane item."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        """Raise :class:`LaneCancelled` if cancellation was requested."""
        if self._event.is_set():
            raise LaneCancelled("lane item cancelled")


@dataclass
class LaneItem:
    fn: Callable[[CancelToken], Any]
    priority: Priority = Priority.TASK
    name: str = ""
    token: CancelToken = field(default_factory=CancelToken)
    on_done: Optional[Callable[[Any, Optional[BaseException]], None]] = None
    enqueued_at: float = field(default_factory=time)


class LaneQueue:
    """Serial priority lane with cooperative cancellation."""

    def __init__(self, bus=None, flush_on_interrupt: bool = True) -> None:
        self._pq: "queue.PriorityQueue[tuple]" = queue.PriorityQueue()
        self._seq = itertools.count()
        self._running = False
        self._worker: Optional[threading.Thread] = None
        self._current_token: Optional[CancelToken] = None
        self._current_lock = threading.Lock()
        self._interrupt_hooks: List[Callable[[], None]] = []
        self._flush_on_interrupt = flush_on_interrupt
        self.bus = bus or get_bus()

    # -- lifecycle -----------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker = threading.Thread(target=self._worker_loop, daemon=True,
                                        name="jarvis-lane")
        self._worker.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._running = False
        if self._worker is not None:
            self._worker.join(timeout=timeout)
            self._worker = None

    @property
    def running(self) -> bool:
        return self._running

    def qsize(self) -> int:
        return self._pq.qsize()

    # -- submission ----------------------------------------------------
    def submit(self, fn: Callable[[CancelToken], Any],
               priority: Priority = Priority.TASK,
               name: str = "",
               on_done: Optional[Callable[[Any, Optional[BaseException]], None]] = None,
               ) -> CancelToken:
        """Enqueue ``fn``; returns its :class:`CancelToken`."""
        item = LaneItem(fn=fn, priority=priority, name=name or getattr(fn, "__name__", "task"),
                        on_done=on_done)
        self._pq.put((int(priority), next(self._seq), item))
        return item.token

    # -- interruption --------------------------------------------------
    def on_interrupt(self, fn: Callable[[], None]) -> Callable[[], None]:
        """Register a hook fired on interrupt (e.g. TTS stop)."""
        self._interrupt_hooks.append(fn)
        return fn

    def interrupt(self, reason: str = "") -> None:
        """Cancel the running item, fire hooks, optionally flush the queue."""
        with self._current_lock:
            tok = self._current_token
        if tok is not None:
            tok.cancel()
        for hook in self._interrupt_hooks:
            try:
                hook()
            except Exception:
                logger.exception("interrupt hook %r crashed", hook)
        if self._flush_on_interrupt:
            self._flush_queued()
        try:
            self.bus.emit(Interrupt(reason=reason))
        except Exception:
            logger.exception("bus emit failed on interrupt")

    def _flush_queued(self) -> None:
        """Drop queued TASK/BACKGROUND items; keep INTERRUPT/CONFIRM."""
        keep = []
        while True:
            try:
                _prio, _seq, item = self._pq.get_nowait()
            except queue.Empty:
                break
            if item.priority in (Priority.INTERRUPT, Priority.CONFIRM):
                keep.append((_prio, _seq, item))
            else:
                item.token.cancel()
        for entry in keep:
            self._pq.put(entry)

    # -- worker --------------------------------------------------------
    def _worker_loop(self) -> None:
        while self._running:
            try:
                _prio, _seq, item = self._pq.get(timeout=0.1)
            except queue.Empty:
                continue
            if item.token.cancelled:
                self._pq.task_done()
                continue
            with self._current_lock:
                self._current_token = item.token
            result, exc = None, None
            try:
                result = item.fn(item.token)
            except LaneCancelled:
                exc = LaneCancelled("cancelled")
            except Exception as e:  # noqa: BLE001 - isolate task crashes
                exc = e
                logger.exception("lane item %r crashed", item.name)
                try:
                    self.bus.emit(Error(where=f"lane:{item.name}", message=str(e)))
                except Exception:
                    logger.exception("bus emit failed for lane error")
            finally:
                with self._current_lock:
                    self._current_token = None
                if item.on_done is not None:
                    try:
                        item.on_done(result, exc)
                    except Exception:
                        logger.exception("on_done hook crashed for %r", item.name)
                self._pq.task_done()
