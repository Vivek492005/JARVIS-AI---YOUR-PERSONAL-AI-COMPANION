"""SQLite memory provider (Supermemory integration, Phase A).

Wraps the existing :py:class:`~jarvis.brain.memory.store.MemoryStore`
behind the :py:class:`~jarvis.brain.memory.provider.MemoryProvider`
interface. The store itself is NOT modified — this is a pure adapter.

Used as the always-available fallback inside
:py:class:`~jarvis.brain.memory.hybrid.HybridProvider`.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from jarvis.brain.memory.provider import Memory, MemoryProvider, Profile
from jarvis.brain.memory.retrieval import Retriever
from jarvis.brain.memory.store import MemoryStore
from jarvis.brain.memory.write_policy import (
    WriteRequest,
    contains_sensitive,
    validate_write,
)

logger = logging.getLogger(__name__)


class SQLiteProvider(MemoryProvider):
    """MemoryProvider backed by the local SQLite MemoryStore."""

    name = "sqlite"

    def __init__(self, path: Optional[Path] = None) -> None:
        self._store = MemoryStore(path)
        self._retriever = Retriever(self._store)

    # -- MemoryProvider ------------------------------------------------

    def add(self, text: str, metadata: Optional[Dict[str, str]] = None) -> str:
        text = (text or "").strip()
        if not text:
            raise ValueError("empty memory text")
        # Sensitive check on the RAW text first: splitting on ':' would
        # consume the very separator the blocklist patterns look for.
        hit = contains_sensitive(text)
        if hit:
            raise ValueError(hit)
        key, value = _split_key_value(text)
        source = (metadata or {}).get("source", "user")
        req = WriteRequest(key=key, value=value, source=source)
        err = validate_write(req)
        if err:
            raise ValueError(err)
        fid = self._store.add_fact(key, value, source=source)
        # Also log the episode so export() shows conversational context.
        self._store.add_episode("user", text, session="provider")
        return str(fid)

    def search(self, query: str, limit: int = 5) -> List[Memory]:
        scored = self._retriever.retrieve(query, k=limit)
        return [
            Memory(
                id=str(s.fact.id),
                text=f"{s.fact.key}: {s.fact.value}",
                score=s.score,
                source=s.fact.source,
            )
            for s in scored
        ]

    def forget(self, query: str) -> int:
        return self._store.delete_facts_like(query)

    def profile(self) -> Profile:
        facts = self._store.all_facts()
        top = [f"{f.key}: {f.value}" for f in facts[:20]]
        return Profile(
            summary=f"{len(facts)} stored facts (local SQLite).",
            facts=top,
        )

    def health(self) -> bool:
        try:
            self._store.all_facts()
            return True
        except Exception:
            logger.exception("sqlite provider health check failed")
            return False

    def export(self) -> str:
        facts = self._store.all_facts()
        eps = self._store.recent_episodes(50)
        out = ["# MEMORY EXPORT (sqlite)", "## Facts"]
        out += [f"- [{f.source}] {f.key}: {f.value}" for f in facts]
        out.append("## Recent episodes")
        out += [f"- ({e['ts']}) {e['role']}: {e['text'][:120]}" for e in eps]
        return "\n".join(out)

    def wipe(self) -> None:
        self._store.clear_all()

    def close(self) -> None:
        self._store.close()


def _split_key_value(text: str) -> tuple:
    """Split memory text into (key, value).

    Prefers an explicit "key: value" format (used by commands and capture),
    then falls back to "meri/my X hai/is Y" patterns.
    """
    text = text.strip()
    m = re.match(r"^([^:]{1,60}):\s*(.+)$", text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # Capture-template format: "User's <thing> is <value>"
    m = re.match(r"(?i)^User's (.+?)\s+is\s+(.+)$", text)
    if m:
        return f"User's {m.group(1).strip()}", m.group(2).strip()
    m = re.match(r"(?i)^(?:meri|mera|my)\s+(.+?)\s+(?:hai|is)\s+(.+)$", text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    words = text.split()
    key = " ".join(words[:4])
    return key, text
