"""Nightly consolidation (Task 4.4.7): episodes -> summary proposals.

The job reads recent episodes and produces *proposed* MEMORY.md lines.
Proposals are NEVER auto-written — the user approves them (via the profile
store's ``append_approved``). The summarizer is pluggable; the default is
extractive so the job runs with no LLM.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Callable, List, Optional

from jarvis.brain.memory.store import MemoryStore

logger = logging.getLogger(__name__)

_STOP = frozenset(
    "ka kya hai aur ko ne se me par ke ki ko ya the a an is are was were to of in on for".split())


def _keywords(texts: List[str], n: int = 8) -> List[str]:
    words = []
    for t in texts:
        words += [w.lower() for w in re.findall(r"[a-zA-Z]{4,}", t or "")]
    words = [w for w in words if w not in _STOP]
    return [w for w, _ in Counter(words).most_common(n)]


def extractive_proposals(texts: List[str]) -> List[str]:
    """Cheap proposal generator: frequent distinctive keywords as topics."""
    kws = _keywords(texts)
    if not kws:
        return []
    return [f"Recent activity involved: {', '.join(kws[:6])}"]


class Consolidator:
    """Builds MEMORY.md proposals from recent episodes."""

    def __init__(
        self,
        store: MemoryStore,
        proposer: Optional[Callable[[List[str]], List[str]]] = None,
    ) -> None:
        self.store = store
        self.proposer = proposer or extractive_proposals

    def run(self, since_ts: str = "", limit: int = 200) -> List[str]:
        eps = (self.store.episodes_since(since_ts) if since_ts
               else self.store.recent_episodes(limit))
        texts = [f"{e['role']}: {e['text']}" for e in eps
                 if e["role"] in ("user", "assistant")]
        if not texts:
            return []
        proposals = self.proposer(texts)
        logger.info("consolidation produced %d proposals from %d episodes",
                    len(proposals), len(texts))
        return proposals
