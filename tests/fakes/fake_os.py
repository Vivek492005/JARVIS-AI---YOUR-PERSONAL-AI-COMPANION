"""FakeOS — dry-run OS adapter for integration tests.

Patches :py:func:`jarvis.tools.actions.execute_tool_raw` so the policy
gate still runs for real (verdicts, confirmations, denials, audit) but
nothing touches the OS. Every attempted action is recorded in
:py:attr:`actions` as ``(tool_name, args)`` tuples; canned results can
be set per tool.

Usage::

    with FakeOS() as fake:
        router.handle("open youtube")
    assert fake.actions == [("open_website", {"url_or_name": "https://www.youtube.com"})]
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from unittest import mock


class FakeOS:
    """Dry-run adapter: records actions, executes nothing."""

    def __init__(
        self, results: Optional[Dict[str, Any]] = None, default_result: str = "[fake-os] ok"
    ) -> None:
        self._results = results or {}
        self._default = default_result
        self.actions: List[Tuple[str, Dict[str, Any]]] = []
        self._patcher: Optional[mock._patch] = None

    def _fake_execute(self, tool_name: str, args: Dict[str, Any], *a, **k) -> str:
        self.actions.append((tool_name, dict(args or {})))
        res = self._results.get(tool_name, self._default)
        return res(args) if callable(res) else res

    def __enter__(self) -> "FakeOS":
        self._patcher = mock.patch(
            "jarvis.tools.actions.execute_tool_raw", side_effect=self._fake_execute
        )
        self._patcher.start()
        return self

    def __exit__(self, *exc) -> None:
        if self._patcher is not None:
            self._patcher.stop()
            self._patcher = None

    def action_names(self) -> List[str]:
        return [name for name, _ in self.actions]


__all__ = ["FakeOS"]
