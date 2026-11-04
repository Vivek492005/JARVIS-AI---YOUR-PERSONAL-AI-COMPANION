"""Hybrid memory provider (whole-brain integration, Phase A).

:class:`HybridProvider` tries the semantic backend (Supermemory) first and
falls back to the local SQLite provider on ANY failure. This is the
fail-open guarantee: if the Supermemory server is down, unreachable, or
misconfigured, JARVIS behaves exactly as before — no turn ever crashes
because of memory.

``backend_used`` reports which backend served the last call, so the agent
can log it (and the user can see it via ``memory status``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from jarvis.brain.memory.provider import Memory, MemoryProvider, Profile
from jarvis.brain.memory.sqlite_provider import SQLiteProvider
from jarvis.brain.memory.supermemory_provider import (
    SupermemoryError,
    SupermemoryProvider,
)

logger = logging.getLogger(__name__)


class HybridProvider(MemoryProvider):
    """Semantic-first, SQLite-always memory provider."""

    name = "hybrid"

    def __init__(
        self,
        sqlite_path: Optional[Path] = None,
        supermemory: Optional[SupermemoryProvider] = None,
        semantic_enabled: bool = True,
    ) -> None:
        self.sqlite = SQLiteProvider(sqlite_path)
        self.semantic = supermemory or SupermemoryProvider()
        self.semantic_enabled = semantic_enabled
        self._last_backend = "sqlite"

    # -- internals ------------------------------------------------------

    def _semantic_ok(self) -> bool:
        return self.semantic_enabled and self.semantic.health()

    def _run(self, op: str, *args, **kwargs):
        """Run ``op`` on semantic first, SQLite on any failure."""
        if self.semantic_enabled:
            try:
                result = getattr(self.semantic, op)(*args, **kwargs)
                self._last_backend = "supermemory"
                return result
            except Exception as e:
                logger.warning(
                    "supermemory %s failed (%s); falling back to sqlite", op, e
                )
        result = getattr(self.sqlite, op)(*args, **kwargs)
        self._last_backend = "sqlite"
        return result

    # -- MemoryProvider -------------------------------------------------

    def add(self, text: str, metadata: Optional[Dict[str, str]] = None) -> str:
        # Write to BOTH backends so the local store stays a complete
        # fallback even after the server comes back. Semantic failure
        # must never lose the write.
        sid = self._run("add", text, metadata)
        if self._last_backend == "supermemory":
            try:
                self.sqlite.add(text, metadata)
            except Exception:
                logger.exception("sqlite mirror-write failed after semantic add")
        return sid

    def search(self, query: str, limit: int = 5) -> List[Memory]:
        return self._run("search", query, limit)

    def forget(self, query: str) -> int:
        # Forget on both so nothing lingers in the fallback store.
        total = 0
        if self.semantic_enabled:
            try:
                total += self.semantic.forget(query)
                self._last_backend = "supermemory"
            except Exception as e:
                logger.warning("supermemory forget failed (%s); sqlite only", e)
                self._last_backend = "sqlite"
        try:
            total += self.sqlite.forget(query)
        except Exception:
            logger.exception("sqlite forget failed")
        return total

    def profile(self) -> Profile:
        return self._run("profile")

    def health(self) -> bool:
        # Hybrid is healthy if EITHER backend works; sqlite is local so
        # this is effectively always True — which is the point.
        try:
            if self.semantic_enabled and self.semantic.health():
                return True
        except Exception:
            logger.debug("semantic health check failed; using sqlite")
        return self.sqlite.health()

    def export(self) -> str:
        parts = []
        if self.semantic_enabled:
            try:
                parts.append(self.semantic.export())
            except Exception as e:
                parts.append(f"# supermemory export failed: {e}")
        parts.append(self.sqlite.export())
        return "\n\n".join(parts)

    def wipe(self) -> None:
        # Wipe both; semantic wipe raises (by design — see
        # SupermemoryProvider.wipe), so do sqlite first and surface the
        # semantic limitation honestly.
        self.sqlite.wipe()
        if self.semantic_enabled:
            try:
                self.semantic.wipe()
            except SupermemoryError as e:
                logger.warning("semantic wipe skipped: %s", e)

    def backend_used(self) -> str:
        return self._last_backend

    def semantic_available(self) -> bool:
        """True when the Supermemory server is currently reachable."""
        try:
            return self.semantic_enabled and self.semantic.health()
        except Exception:
            return False

    def set_semantic_enabled(self, enabled: bool) -> None:
        """Kill-switch: False forces pure-local mode."""
        self.semantic_enabled = enabled
        logger.info("semantic memory %s", "enabled" if enabled else "disabled")

    def close(self) -> None:
        self.sqlite.close()
