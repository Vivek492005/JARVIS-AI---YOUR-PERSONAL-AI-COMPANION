"""Event bus (Master Plan Task 2.2).

Components publish events instead of calling each other directly. The bus
is threading-first (the app is threading-based): ``emit()`` dispatches
synchronously in the caller's thread, each subscriber isolated in
try/except so one crashing handler never takes down the emitter or the
other subscribers.

Async subscribers are supported too: attach an asyncio loop with
:meth:`Bus.attach_loop` and they are scheduled via
``asyncio.run_coroutine_threadsafe``; without a loop they are skipped
with a debug log. :meth:`Bus.aemit` is the native-async variant.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from time import time
from typing import Any, Callable, DefaultDict, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


def new_trace() -> str:
    """Create a fresh trace id linking one utterance to all its events."""
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@dataclass
class Event:
    trace: str = ""
    ts: float = field(default_factory=time)


@dataclass
class WakeDetected(Event):
    wake_word: str = ""


@dataclass
class UtterancePartial(Event):
    text: str = ""


@dataclass
class UtteranceFinal(Event):
    text: str = ""
    lang: str = "hi-en"


@dataclass
class AgentThinking(Event):
    status: str = ""


@dataclass
class ToolRequested(Event):
    tool: str = ""
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfirmationRequested(Event):
    tool: str = ""
    question: str = ""


@dataclass
class ConfirmationAnswered(Event):
    confirmed: bool = False
    tool: str = ""


@dataclass
class ToolFinished(Event):
    tool: str = ""
    ok: bool = True
    result: str = ""


@dataclass
class SpeechStarted(Event):
    text: str = ""


@dataclass
class SpeechStopped(Event):
    interrupted: bool = False


@dataclass
class Interrupt(Event):
    reason: str = ""


@dataclass
class Error(Event):
    where: str = ""
    message: str = ""


@dataclass
class StatusChanged(Event):
    status: str = ""


# ---------------------------------------------------------------------------
# Bus
# ---------------------------------------------------------------------------

Subscriber = Callable[[Event], Any]


class Bus:
    """Thread-safe publish/subscribe bus."""

    def __init__(self) -> None:
        self._subs: DefaultDict[Type[Event], List[Subscriber]] = defaultdict(list)
        self._all: List[Subscriber] = []
        self._lock = threading.RLock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # -- subscription ----------------------------------------------------
    def on(self, etype: Type[Event], fn: Subscriber) -> Subscriber:
        """Subscribe ``fn`` to ``etype``. Returns ``fn`` (decorator-friendly)."""
        with self._lock:
            self._subs[etype].append(fn)
        return fn

    def off(self, etype: Type[Event], fn: Subscriber) -> None:
        with self._lock:
            try:
                self._subs[etype].remove(fn)
            except ValueError:
                pass
        with self._lock:
            try:
                self._all.remove(fn)
            except ValueError:
                pass

    def on_all(self, fn: Subscriber) -> Subscriber:
        """Subscribe ``fn`` to every event type (e.g. the WS event stream)."""
        with self._lock:
            self._all.append(fn)
        return fn

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Attach an asyncio loop used to schedule coroutine subscribers."""
        with self._lock:
            self._loop = loop

    # -- publishing ------------------------------------------------------
    def emit(self, ev: Event) -> None:
        """Dispatch ``ev`` to subscribers of its exact type.

        Synchronous: runs in the caller's thread. A raising subscriber is
        logged and skipped — it never breaks the emitter or the others.
        Coroutine subscribers are scheduled on the attached loop (if any).
        """
        with self._lock:
            subs = list(self._subs.get(type(ev), [])) + list(self._all)
            loop = self._loop
        for fn in subs:
            try:
                if inspect.iscoroutinefunction(fn):
                    if loop is not None:
                        asyncio.run_coroutine_threadsafe(fn(ev), loop)
                    else:
                        logger.debug("no loop attached; skipping async sub %r", fn)
                else:
                    fn(ev)
            except Exception:
                logger.exception("event subscriber %r crashed on %r", fn, ev)

    async def aemit(self, ev: Event) -> None:
        """Async variant: awaits coroutine subscribers inline."""
        with self._lock:
            subs = list(self._subs.get(type(ev), [])) + list(self._all)
        for fn in subs:
            try:
                res = fn(ev)
                if inspect.isawaitable(res):
                    await res
            except Exception:
                logger.exception("event subscriber %r crashed on %r", fn, ev)


# ---------------------------------------------------------------------------
# Process-wide default bus
# ---------------------------------------------------------------------------

_default_bus: Optional[Bus] = None
_default_lock = threading.Lock()


def get_bus() -> Bus:
    """Return the process-wide default bus (created on first use)."""
    global _default_bus
    with _default_lock:
        if _default_bus is None:
            _default_bus = Bus()
        return _default_bus


def reset_bus() -> Bus:
    """Replace the default bus (used by tests to isolate event flow)."""
    global _default_bus
    with _default_lock:
        _default_bus = Bus()
        return _default_bus
