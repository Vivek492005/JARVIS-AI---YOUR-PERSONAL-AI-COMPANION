"""FakeLLM — scripted LLM provider with recorded JSON fixtures.

Two modes:
  * scripted: ``FakeLLM(script=[Completion(...), ProviderError(...), ...])``
    pops one item per ``complete()`` call (last item repeats);
  * fixture: ``FakeLLM.from_fixture({...})`` maps the last user message
    to a canned reply, e.g. loaded from a recorded JSON file.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from jarvis.brain.providers.base import Completion, LLMProvider, ToolCall


class FakeLLM:
    """Deterministic stand-in for any LLMProvider."""

    def __init__(
        self,
        name: str = "fake-llm",
        script: Optional[List[Any]] = None,
        fixtures: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._name = name
        self._script = list(script or [])
        self._fixtures = fixtures or {}
        self.calls: List[Dict[str, Any]] = []
        self.attempts = 0

    @property
    def name(self) -> str:
        return self._name

    @classmethod
    def from_fixture_json(cls, path: str, name: str = "fake-llm") -> "FakeLLM":
        with open(path, encoding="utf-8") as f:
            return cls(name=name, fixtures=json.load(f))

    @staticmethod
    def _coerce(item: Any, name: str) -> Completion:
        if isinstance(item, Completion):
            item.provider = item.provider or name
            return item
        if isinstance(item, dict):
            calls = [
                ToolCall(id=c.get("id", f"call_{i}"), name=c["name"], args=c.get("args", {}))
                for i, c in enumerate(item.get("tool_calls", []))
            ]
            return Completion(text=item.get("text", ""), tool_calls=calls, provider=name)
        raise TypeError(f"bad script item: {item!r}")

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
    ) -> Completion:
        self.attempts += 1
        self.calls.append({"messages": messages, "tools": tools, "temperature": temperature})
        if self._script:
            item = self._script.pop(0) if len(self._script) > 1 else self._script[0]
            if isinstance(item, Exception):
                raise item
            return self._coerce(item, self._name)
        # Fixture mode: match on the last user message.
        user_text = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_text = m.get("content", "")
                break
        if user_text in self._fixtures:
            return self._coerce(self._fixtures[user_text], self._name)
        return Completion(text=f"[fake-llm] no fixture for {user_text!r}", provider=self._name)

    def health(self) -> bool:
        return True


# Re-export the provider protocol for typing convenience.
__all__ = ["FakeLLM", "LLMProvider"]
