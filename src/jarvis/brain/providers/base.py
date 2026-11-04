"""Provider interfaces (Master Plan Task 2.5).

Design note: the plan sketches these as ``async`` protocols, but the
runtime is deliberately threading-based (Task 2.3 decision: Bus and
LaneQueue are sync, the whole app runs on worker threads). These
protocols are therefore **synchronous** — same shape and semantics as
the plan (``name`` / chat / ``health``), minus the event loop. If the
runtime ever moves to asyncio, the seam to change is this module.

``LLMProvider.complete`` performs ONE round-trip (system+history+user
messages, optional tool specs) and returns a normalized
:py:class:`Completion`. The tool-dispatch loop stays in
:py:class:`AIAgent` — it owns policy gating, taint tracking and audit.
Retry / fallback / circuit-breaking across providers lives in
:py:mod:`jarvis.brain.providers.chain`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class ToolCall:
    """A normalized tool call requested by the model."""

    id: str
    name: str
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Completion:
    """One normalized model round-trip."""

    text: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    provider: str = ""
    raw: Any = None  # provider-native response, for debugging


class LLMProvider(Protocol):
    """A chat-completion backend behind one interface."""

    @property
    def name(self) -> str: ...

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
    ) -> Completion:
        """One chat round-trip. Raises ProviderError (or subclass) on failure."""
        ...

    def health(self) -> bool:
        """Cheap liveness probe. Never raises."""
        ...


class STTProvider(Protocol):
    """Speech-to-text backend (wired up in Phase 3, Voice 2.0)."""

    @property
    def name(self) -> str: ...

    def transcribe(self, audio: bytes, language: str = "hi-en") -> str: ...


class TTSProvider(Protocol):
    """Text-to-speech backend (wired up in Phase 3, Voice 2.0)."""

    @property
    def name(self) -> str: ...

    def synth(self, text: str, voice: Optional[str] = None) -> bytes:
        """Synthesize speech; returns raw audio bytes."""
        ...
