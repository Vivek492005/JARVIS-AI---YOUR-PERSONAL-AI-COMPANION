"""Local heuristic provider — the final fallback (Master Plan Task 2.5.5).

This is NOT an "LLM fallback": it is the deterministic heuristic
engine that Task 2.6 promotes into the reflex (System-1) layer. It is
modelled as a provider only so the chain manager treats it uniformly —
always healthy, never retried, and its use is reported honestly as
"local mode" rather than silent quality degradation.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from jarvis.brain.providers.base import Completion


class LocalHeuristicProvider:
    """Wraps the agent's heuristic engine as a chain terminal."""

    name = "local-heuristic"

    def __init__(self, handler: Callable[[str], str]) -> None:
        self._handler = handler

    def complete(self, messages: List[Dict[str, Any]],
                 tools: Optional[List[Dict[str, Any]]] = None,
                 temperature: float = 0.3) -> Completion:
        # The heuristic engine works on the latest user utterance only.
        text = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                text = m.get("content", "")
                break
        return Completion(text=self._handler(text or ""),
                          tool_calls=[], provider=self.name)

    def health(self) -> bool:
        return True
