"""Context management (Master Plan Task 4.5).

Rolling conversation window + summarization of old turns, tool-output
truncation (head+tail), per-tier token budgets, and a ``last_entities``
table so references like "wo wala file" resolve.

Token counting is approximate (chars // 4) — good enough for budgeting;
the plan does not require a tokenizer dependency.
"""

from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token for Latin scripts)."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def truncate_tool_output(text: str, max_chars: int = 2000) -> str:
    """Keep head+tail of long tool output so the middle doesn't eat context."""
    if len(text) <= max_chars:
        return text
    head = max_chars * 3 // 5
    tail = max_chars - head - 40
    return (text[:head]
            + f"\n... [truncated {len(text) - head - tail} chars] ...\n"
            + text[-tail:])


@dataclass
class Turn:
    role: str  # "user" | "assistant" | "tool"
    text: str
    tokens: int = 0

    def __post_init__(self) -> None:
        if not self.tokens:
            self.tokens = estimate_tokens(self.text)


@dataclass
class Summary:
    """A compressed replacement for evicted turns."""
    text: str
    turns_covered: int = 0


class LastEntities:
    """Resolves "wo wala file" — remembers the last file/URL/app/note."""

    _KINDS = ("file", "url", "app", "note")

    def __init__(self) -> None:
        self._ents: Dict[str, str] = {}

    def record(self, kind: str, value: str) -> None:
        if kind in self._KINDS and value:
            self._ents[kind] = value

    def get(self, kind: str) -> Optional[str]:
        return self._ents.get(kind)

    def resolve_reference(self, text: str) -> Optional[str]:
        """If the text is a bare demonstrative reference, return the entity."""
        t = text.strip().lower()
        if re.fullmatch(r"(wo|woh|that|it|us|usko|ise|is)\s*(wala|wali|wale)?\s*(file|url|link|app|note)?", t):
            # Prefer an explicit kind word, else fall back in priority order.
            for kind in self._KINDS:
                if kind in t and self._ents.get(kind):
                    return self._ents[kind]
            for kind in ("file", "url", "app", "note"):
                if self._ents.get(kind):
                    return self._ents[kind]
        return None


class ContextManager:
    """Owns the conversation context for one session.

    * ``max_turns`` hard cap on kept turns (rolling window).
    * ``token_budget`` soft cap; older turns are summarized when exceeded.
    * ``summarizer``: pluggable ``(List[Turn]) -> str``; the default is a
      cheap extractive summary (first user intent + tool outcomes) so the
      loop works with no LLM. A real summarizer can be injected.
    """

    def __init__(
        self,
        max_turns: int = 30,
        token_budget: int = 6000,
        summarizer: Optional[Callable[[List[Turn]], str]] = None,
    ) -> None:
        self.max_turns = max_turns
        self.token_budget = token_budget
        self._summarizer = summarizer or self._default_summarizer
        self.turns: Deque[Turn] = deque()
        self.summaries: List[Summary] = []
        self.entities = LastEntities()
        self._tokens = 0

    # -- mutation ------------------------------------------------------

    def add_turn(self, role: str, text: str) -> None:
        turn = Turn(role=role, text=text)
        self.turns.append(turn)
        self._tokens += turn.tokens
        self._enforce_limits()

    def add_tool_observation(self, tool: str, result: str) -> None:
        self.add_turn("tool", f"[{tool}] {truncate_tool_output(result)}")

    # -- limits --------------------------------------------------------

    def _enforce_limits(self) -> None:
        while (len(self.turns) > self.max_turns or self._tokens > self.token_budget) \
                and len(self.turns) > 4:
            # Summarize the oldest third, keep the newest two-thirds.
            n = max(1, len(self.turns) // 3)
            old = [self.turns.popleft() for _ in range(n)]
            self._tokens -= sum(t.tokens for t in old)
            summary = self._summarizer(old)
            self.summaries.append(Summary(text=summary, turns_covered=n))
            logger.debug("summarized %d turns", n)

    @staticmethod
    def _default_summarizer(turns: List[Turn]) -> str:
        intents = [t.text for t in turns if t.role == "user"]
        outcomes = [t.text for t in turns if t.role == "tool"]
        bits = []
        if intents:
            bits.append("user asked: " + "; ".join(i[:80] for i in intents[:3]))
        if outcomes:
            bits.append("tools: " + "; ".join(o[:80] for o in outcomes[:3]))
        return "Earlier: " + " | ".join(bits) if bits else "Earlier: (no notable turns)"

    # -- read ----------------------------------------------------------

    def build_messages(self, system_prompt: str) -> List[Dict[str, str]]:
        """Assemble the LLM message list: system + summaries + turns."""
        msgs: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for s in self.summaries:
            msgs.append({"role": "system",
                         "content": f"[summary of {s.turns_covered} older turns] {s.text}"})
        for t in self.turns:
            msgs.append({"role": t.role if t.role != "tool" else "user",
                         "content": t.text})
        return msgs

    @property
    def token_count(self) -> int:
        return self._tokens + sum(estimate_tokens(s.text) for s in self.summaries)
