"""Memory retrieval (Task 4.4.3).

score = similarity x recency x importance; top-k facts go into the prompt.

Similarity is a lightweight token-overlap score (Jaccard over normalized
tokens) — no embedding dependency, so memory never needs the cloud. An
optional embedder hook (``similarity_fn``) can replace it later without
changing callers.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from jarvis.brain.memory.store import Fact, MemoryStore

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set:
    return set(_TOKEN_RE.findall((text or "").lower()))


def jaccard_similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _recency_factor(last_used: str, now: float) -> float:
    try:
        ts = time.mktime(time.strptime(last_used, "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, TypeError):
        return 0.5
    age_days = max(0.0, (now - ts) / 86400.0)
    # Half-life ~30 days.
    return 0.5 ** (age_days / 30.0)


@dataclass
class ScoredFact:
    fact: Fact
    score: float


class Retriever:
    """Top-k fact retrieval for prompt injection."""

    def __init__(
        self,
        store: MemoryStore,
        similarity_fn: Optional[Callable[[str, str], float]] = None,
    ) -> None:
        self.store = store
        self.similarity_fn = similarity_fn or jaccard_similarity

    def retrieve(self, query: str, k: int = 5) -> List[ScoredFact]:
        now = time.time()
        scored = []
        for fact in self.store.all_facts():
            sim = self.similarity_fn(query, f"{fact.key} {fact.value}")
            if sim <= 0:
                continue
            rec = _recency_factor(fact.last_used, now)
            score = sim * rec * max(0.05, fact.importance)
            scored.append(ScoredFact(fact=fact, score=score))
        scored.sort(key=lambda s: s.score, reverse=True)
        top = scored[:k]
        for s in top:
            self.store.touch_fact(s.fact.id)
        return top

    def format_for_prompt(self, query: str, k: int = 5) -> List[str]:
        return [f"{s.fact.key}: {s.fact.value}"
                for s in self.retrieve(query, k)]
