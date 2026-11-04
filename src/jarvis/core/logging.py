"""Structured observability (Master Plan Task 2.7).

* :py:func:`setup_logging` — stdlib logging with an optional JSON
  formatter (the plan names structlog; stdlib keeps the dependency
  footprint at zero and the output is the same shape).
* Trace IDs — one per utterance, via :py:func:`new_trace_id` and the
  :py:mod:`contextvars` context, so every log line for a turn carries
  the same ``trace`` field. (The event bus has its own ``trace`` field
  on events — see :py:mod:`jarvis.core.events`.)
* :py:class:`StageTimer` — lightweight stage timings (reflex match,
  LLM round-trip, tool dispatch, total). Full pipeline stages
  (capture/VAD/STT/TTS-first-audio) arrive with Phase 3's voice
  pipeline; the timer already supports them.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from typing import Dict

_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("jarvis_trace_id", default="")


def new_trace_id() -> str:
    """Generate a new trace id (hex, 16 chars)."""
    return uuid.uuid4().hex[:16]


def get_trace_id() -> str:
    return _trace_id.get()


def set_trace_id(trace_id: str) -> None:
    _trace_id.set(trace_id)


class JsonFormatter(logging.Formatter):
    """Single-line JSON log records: ts, level, logger, msg, trace."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "trace": getattr(record, "trace", None) or get_trace_id() or None,
        }
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _TraceFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace = get_trace_id() or None
        return True


def setup_logging(level: str = "INFO", json_output: bool = False, stream=None) -> None:
    """Configure the ``jarvis`` root logger (idempotent)."""
    root = logging.getLogger("jarvis")
    if getattr(root, "_jarvis_configured", False):
        return
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler(stream or sys.stderr)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-7s %(name)s [%(trace)s] %(message)s",
                defaults={"trace": "-"},
            )
        )
    handler.addFilter(_TraceFilter())
    root.addHandler(handler)
    root.propagate = False
    root._jarvis_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"jarvis.{name}")


class StageTimer:
    """Collect per-stage timings for one utterance turn.

    Usage::

        with StageTimer() as st:
            with st.stage("reflex_match"):
                ...
        st.timings  # {"reflex_match": 12.3(ms), ...}
    """

    def __init__(self) -> None:
        self.timings: Dict[str, float] = {}
        self._stack: list = []

    def __enter__(self) -> "StageTimer":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc) -> None:
        self.timings["total"] = (time.perf_counter() - self._t0) * 1000.0

    class _Stage:
        def __init__(self, timer: "StageTimer", name: str):
            self._timer = timer
            self._name = name

        def __enter__(self):
            self._t0 = time.perf_counter()
            return self

        def __exit__(self, *exc):
            ms = (time.perf_counter() - self._t0) * 1000.0
            self._timer.timings[self._name] = ms

    def stage(self, name: str) -> "_Stage":
        return StageTimer._Stage(self, name)
