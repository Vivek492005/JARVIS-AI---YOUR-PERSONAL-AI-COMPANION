"""Backend protocols + injection point for perception/control surfaces.

Every surface (UIA, screen, OCR, browser, VLM, apps, context) talks to a
*backend* behind a small protocol. Real backends need Windows and optional
third-party libs (pywinauto, mss, playwright, pytesseract) — they are
lazy-imported and raise :class:`BackendUnavailable` off-platform or when
the dependency is missing. Tests inject fakes via :func:`set_backend`
(see ``tests/fakes/fake_desktop.py``).

This keeps every Phase-5 module unit-testable on headless Linux while the
real implementations stay thin Windows shims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


class BackendUnavailable(RuntimeError):
    """Raised when no backend is registered or the real one can't load."""


# ---------------------------------------------------------------------------
# Backend registry (injection point)
# ---------------------------------------------------------------------------

_BACKENDS: Dict[str, Any] = {}


def set_backend(name: str, backend: Any) -> None:
    """Register (or replace) a backend. Used by real-backend loaders and
    by tests to inject fakes."""
    _BACKENDS[name] = backend


def get_backend(name: str) -> Any:
    """Return the registered backend, or raise BackendUnavailable."""
    try:
        return _BACKENDS[name]
    except KeyError:
        raise BackendUnavailable(
            f"no backend registered for {name!r} (Windows + optional dependency required)"
        ) from None


def clear_backends() -> None:
    """Forget all backends (tests)."""
    _BACKENDS.clear()


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass
class WindowInfo:
    handle: int
    title: str
    process: str = ""
    visible: bool = True


@dataclass
class ElementNode:
    element_id: str
    role: str
    name: str
    automation_id: str = ""
    enabled: bool = True
    bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, w, h
    children: List["ElementNode"] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Protocols (duck-typed; real backends implement these methods)
# ---------------------------------------------------------------------------


class UIABackend:
    """pywinauto/UIA shim interface."""

    def list_windows(self) -> List[WindowInfo]: ...
    def get_tree(self, handle: int, depth: int = 3) -> ElementNode: ...
    def find(
        self,
        handle: int,
        name: Optional[str] = None,
        role: Optional[str] = None,
        automation_id: Optional[str] = None,
    ) -> Optional[ElementNode]: ...
    def invoke(self, element_id: str) -> bool: ...
    def get_text(self, element_id: str) -> str: ...
    def set_text(self, element_id: str, value: str) -> bool: ...


class ScreenBackend:
    """mss-style capture shim."""

    def capture_window(self, handle: int) -> bytes: ...  # PNG bytes
    def capture_region(self, x: int, y: int, w: int, h: int) -> bytes: ...


class OCRBackend:
    def read_text(self, image_png: bytes, lang: str = "en") -> str: ...


class BrowserBackend:
    """Playwright-style DOM automation shim (dedicated profile)."""

    def open(self, url: str) -> str: ...  # -> page title / status
    def snapshot(self) -> str: ...  # accessibility tree text
    def click(self, ref: str) -> str: ...
    def fill(self, ref: str, value: str) -> str: ...
    def submit(self, ref: Optional[str] = None) -> str: ...
    @property
    def current_url(self) -> str: ...


class VLMBackend:
    """Set-of-marks VLM shim: returns the chosen mark index (1-based)."""

    def pick_element(self, image_png: bytes, prompt: str, max_marks: int = 12) -> int: ...


class ContextBackend:
    def active_window(self) -> WindowInfo: ...
    def selected_text(self) -> str: ...
    def clipboard_has_text(self) -> bool: ...
    def clipboard_text(self) -> str: ...


# App adapters ---------------------------------------------------------------


class VSCodeBackend:
    def open_path(self, path: str) -> str: ...
    def run_task(self, task: str, folder: str) -> str: ...


class OfficeBackend:
    def open_document(self, path: str) -> str: ...
    def read_cells(self, path: str, sheet: str = "", cell_range: str = "") -> str: ...
    def save_document(self, path: str) -> str: ...


class SpotifyBackend:
    def control(self, action: str, query: str = "") -> str: ...


# ---------------------------------------------------------------------------
# Real-backend loaders (lazy; Windows-only)
# ---------------------------------------------------------------------------


def _missing(dep: str) -> Callable[[], Any]:
    def _raise(*a: Any, **k: Any) -> Any:
        raise BackendUnavailable(f"real backend needs {dep} on Windows; nothing registered")

    return _raise


def load_real_uia() -> UIABackend:
    try:
        import pywinauto  # noqa: F401
    except ImportError:
        raise BackendUnavailable("pywinauto not installed") from None
    raise BackendUnavailable("real UIA backend: Windows-only, not implemented on this host")


def load_real_screen() -> ScreenBackend:
    try:
        import mss  # noqa: F401
    except ImportError:
        raise BackendUnavailable("mss not installed") from None
    raise BackendUnavailable("real screen backend: Windows-only, not implemented on this host")


def load_real_browser() -> BrowserBackend:
    try:
        import playwright  # noqa: F401
    except ImportError:
        raise BackendUnavailable("playwright not installed") from None
    raise BackendUnavailable("real browser backend: Windows-only, not implemented on this host")
