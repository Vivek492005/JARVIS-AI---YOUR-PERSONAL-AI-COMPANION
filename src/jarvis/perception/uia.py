"""UI Automation layer (Master Plan Task 5.2).

Thin controller over the UIA backend (pywinauto on Windows, fakes in
tests). Provides:

- :meth:`UIAController.list_windows`
- :meth:`UIAController.describe_screen` — compact, token-efficient tree
  of the active window (role, name, id, enabled). Privacy-blocklisted
  windows are refused (Task 5.2.5).
- :meth:`UIAController.find` with an element cache keyed by
  (window handle, element id).
- :meth:`UIAController.invoke` / :meth:`UIAController.get_text` /
  :meth:`UIAController.set_text`.

Risk tagging (Task 5.2.4): ``get_text`` = READ; ``invoke`` = REVERSIBLE,
escalated to DESTRUCTIVE when the button label matches
:data:`DESTRUCTIVE_LABELS` (Delete/Send/Pay/Install/...). The escalation
happens in :func:`jarvis.tools.registry.resolve` via the ``uia_invoke``
special case, mirroring the ``press_hotkey`` precedent.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from jarvis.perception import backends as _backends
from jarvis.perception.backends import ElementNode, WindowInfo
from jarvis.perception.privacy import SensitiveWindowError, check_window
from jarvis.tools.registry import Risk

logger = logging.getLogger(__name__)

# Button labels that escalate invoke() from REVERSIBLE to DESTRUCTIVE.
DESTRUCTIVE_LABELS = frozenset({
    "delete", "remove", "erase", "format",
    "send", "submit", "post", "publish",
    "pay", "buy", "purchase", "checkout",
    "install", "uninstall",
    "ok", "confirm",  # deliberately NOT here: too generic; policy decides
})

# Extra guard: these exact labels are always destructive even as substrings
# of longer names ("Delete all" etc. is covered by substring match below).
_ALWAYS_DESTRUCTIVE = frozenset({
    "delete", "remove", "send", "pay", "buy", "purchase", "install",
    "uninstall", "format", "submit",
})


def invoke_risk_for_label(name: str) -> Risk:
    """Risk tier for invoking a control with the given label."""
    lowered = (name or "").lower()
    if any(lbl in lowered for lbl in _ALWAYS_DESTRUCTIVE):
        return Risk.DESTRUCTIVE
    return Risk.REVERSIBLE


def _compact_node(node: ElementNode, depth: int, out: List[str]) -> None:
    """One line per element: `- [role] 'name' #id (disabled?)`."""
    indent = "  " * depth
    disabled = "" if node.enabled else " [disabled]"
    aid = f" @{node.automation_id}" if node.automation_id else ""
    out.append(f"{indent}- [{node.role}] '{node.name}' #{node.element_id}{aid}{disabled}")


def _walk(node: ElementNode, depth: int, max_depth: int,
          out: List[str]) -> None:
    if depth > max_depth:
        return
    _compact_node(node, depth, out)
    for child in node.children:
        _walk(child, depth + 1, max_depth, out)


class UIAController:
    """UI Automation controller. Backend injected via backends registry."""

    def __init__(self, backend: Optional[object] = None) -> None:
        self._backend = backend
        self._cache: Dict[Tuple[int, str], ElementNode] = {}

    def _be(self):
        return self._backend or _backends.get_backend("uia")

    # -- windows -----------------------------------------------------------
    def list_windows(self) -> List[WindowInfo]:
        return self._be().list_windows()

    def active_window(self) -> WindowInfo:
        """Active window via the context backend (falls back to first)."""
        try:
            ctx = _backends.get_backend("context")
            return ctx.active_window()
        except Exception:
            wins = self.list_windows()
            if not wins:
                raise RuntimeError("no windows available")
            return wins[0]

    # -- describe ----------------------------------------------------------
    def describe_screen(self, handle: Optional[int] = None,
                        depth: int = 3) -> str:
        """Compact tree of the active (or given) window.

        Refuses sensitive windows (password managers, banking, incognito).
        """
        win = self._window(handle)
        check_window(win.title, win.process)
        tree = self._be().get_tree(win.handle, depth)
        lines: List[str] = [
            f"window '{win.title}' (handle={win.handle}, process={win.process})"
        ]
        _walk(tree, 0, depth, lines)
        return "\n".join(lines)

    def _window(self, handle: Optional[int]) -> WindowInfo:
        if handle is not None:
            for w in self.list_windows():
                if w.handle == handle:
                    return w
            raise ValueError(f"no window with handle {handle}")
        return self.active_window()

    # -- find (cached) -----------------------------------------------------
    def find(self, name: Optional[str] = None,
             role: Optional[str] = None,
             automation_id: Optional[str] = None,
             handle: Optional[int] = None) -> Optional[ElementNode]:
        win = self._window(handle)
        check_window(win.title, win.process)
        # Cache key includes the query so repeats are O(1).
        key = (win.handle, f"{name}|{role}|{automation_id}")
        if key in self._cache:
            return self._cache[key]
        el = self._be().find(win.handle, name=name, role=role,
                             automation_id=automation_id)
        if el is not None:
            self._cache[key] = el
        return el

    def clear_cache(self) -> None:
        self._cache.clear()

    # -- actions -----------------------------------------------------------
    def invoke(self, element_id: str) -> str:
        ok = self._be().invoke(element_id)
        return "invoked" if ok else f"invoke failed: unknown element {element_id}"

    def get_text(self, element_id: str) -> str:
        return self._be().get_text(element_id)

    def set_text(self, element_id: str, value: str) -> str:
        ok = self._be().set_text(element_id, value)
        return "text set" if ok else f"set_text failed: unknown element {element_id}"


_CONTROLLER: Optional[UIAController] = None


def controller() -> UIAController:
    """Shared controller instance."""
    global _CONTROLLER
    if _CONTROLLER is None:
        _CONTROLLER = UIAController()
    return _CONTROLLER
