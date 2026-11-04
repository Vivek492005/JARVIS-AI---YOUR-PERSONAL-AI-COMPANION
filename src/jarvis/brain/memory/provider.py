"""Memory provider interface (Supermemory "whole brain" integration, Phase A).

A :class:`MemoryProvider` is a swappable memory backend. The local SQLite
:py:class:`~jarvis.brain.memory.store.MemoryStore` and the Supermemory
semantic server both implement this interface, so callers (recall hooks,
memory commands, profile sync) never touch a backend directly.

Plain dataclasses cross the boundary — no backend-specific types leak out.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Memory:
    """One recalled memory, backend-agnostic."""

    id: str
    text: str
    score: float = 0.0
    source: str = ""  # 'user' | 'confirmed' | 'semantic' | ...
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class Profile:
    """User profile snapshot, backend-agnostic."""

    summary: str = ""
    facts: List[str] = field(default_factory=list)
    raw: Dict[str, object] = field(default_factory=dict)


class MemoryProvider(abc.ABC):
    """Abstract memory backend."""

    name: str = "base"

    @abc.abstractmethod
    def add(self, text: str, metadata: Optional[Dict[str, str]] = None) -> str:
        """Store a memory. Returns the backend's id for it."""

    @abc.abstractmethod
    def search(self, query: str, limit: int = 5) -> List[Memory]:
        """Semantic/keyword search. Returns best matches first."""

    @abc.abstractmethod
    def forget(self, query: str) -> int:
        """Forget memories matching ``query``. Returns count removed."""

    @abc.abstractmethod
    def profile(self) -> Profile:
        """Return the user profile snapshot."""

    @abc.abstractmethod
    def health(self) -> bool:
        """True if the backend is reachable and usable right now."""

    @abc.abstractmethod
    def export(self) -> str:
        """Human-readable dump of everything stored."""

    @abc.abstractmethod
    def wipe(self) -> None:
        """Delete everything stored. Caller must confirm first."""

    # -- optional ------------------------------------------------------

    def backend_used(self) -> str:
        """Name of the backend that served the last call."""
        return self.name
