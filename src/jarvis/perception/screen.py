"""Screen capture + OCR + privacy filter (Master Plan Task 5.3).

- Capture is **active-window only** by default (never full screen unless
  asked), via the screen backend (mss on Windows, fakes in tests).
- Screenshots live in **memory** by default; nothing is written to disk
  unless ``keep_on_disk=True`` is passed, in which case files land in
  ``screenshots/`` and are auto-pruned after 24 h.
- The sensitive-window blocklist (Task 5.2.5, shared via
  :mod:`jarvis.perception.privacy`) **refuses** capture on password
  managers, banking apps and private browsing.
- :func:`read_screen_text` runs OCR (Hindi+English models where
  available) and redacts card-like/secret-like runs. Its tool result is
  marked ``carries_external_data`` so the agent treats it as untrusted
  (Task 1.5 — screen text is an injection source).
"""

from __future__ import annotations

import logging
import os
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Optional, Tuple

from jarvis.perception import backends as _backends
from jarvis.perception.backends import WindowInfo
from jarvis.perception.privacy import (
    check_window,
    redact_text,
)

logger = logging.getLogger(__name__)

# In-memory shot cache: shot_id -> (png_bytes, window_title, ts).
# Bounded so a long session can't grow memory without limit.
_MAX_SHOTS = 20
_SHOTS: "OrderedDict[str, Tuple[bytes, str, float]]" = OrderedDict()
_SHOT_SEQ = 0


def _next_shot_id() -> str:
    global _SHOT_SEQ
    _SHOT_SEQ += 1
    return f"shot-{_SHOT_SEQ:04d}"


def _store_shot(png: bytes, title: str) -> str:
    shot_id = _next_shot_id()
    _SHOTS[shot_id] = (png, title, time.time())
    while len(_SHOTS) > _MAX_SHOTS:
        _SHOTS.popitem(last=False)
    return shot_id


def get_shot(shot_id: str) -> Optional[bytes]:
    """Return cached PNG bytes for a shot id (used by the VLM path)."""
    entry = _SHOTS.get(shot_id)
    return entry[0] if entry else None


def _active_window() -> WindowInfo:
    try:
        ctx = _backends.get_backend("context")
        return ctx.active_window()
    except Exception as e:
        raise RuntimeError(f"no context backend for active window: {e}") from e


def _window_by_handle(handle: int) -> WindowInfo:
    uia = _backends.get_backend("uia")
    for w in uia.list_windows():
        if w.handle == handle:
            return w
    raise ValueError(f"no window with handle {handle}")


class ScreenCapture:
    """Capture + OCR with the privacy filter applied."""

    def __init__(self, screen_backend=None, ocr_backend=None) -> None:
        self._screen = screen_backend
        self._ocr = ocr_backend

    def _screen_be(self):
        return self._screen or _backends.get_backend("screen")

    def _ocr_be(self):
        return self._ocr or _backends.get_backend("ocr")

    def capture(
        self, handle: Optional[int] = None, keep_on_disk: bool = False
    ) -> Dict[str, object]:
        """Capture the active window (or ``handle``) to memory.

        Returns ``{"shot_id": ..., "window": ..., "bytes": N,
        "on_disk": path|None}``. Raises :class:`SensitiveWindowError`
        for blocklisted windows.
        """
        win = _window_by_handle(handle) if handle is not None else _active_window()
        check_window(win.title, win.process)
        png = self._screen_be().capture_window(win.handle)
        shot_id = _store_shot(png, win.title)
        on_disk = None
        if keep_on_disk:
            on_disk = _save_shot(png, shot_id)
        return {"shot_id": shot_id, "window": win.title, "bytes": len(png), "on_disk": on_disk}

    def read_text(self, handle: Optional[int] = None, lang: str = "en") -> str:
        """OCR the active window (or ``handle``); redacted.

        Raises :class:`SensitiveWindowError` for blocklisted windows.
        """
        info = self.capture(handle=handle, keep_on_disk=False)
        png = get_shot(str(info["shot_id"]))
        assert png is not None  # just stored
        text = self._ocr_be().read_text(png, lang=lang)
        return redact_text(text)


def _screenshots_dir() -> Path:
    d = Path(
        os.path.expandvars("%LOCALAPPDATA%/jarvis/screenshots")
        if os.name == "nt"
        else "~/.local/share/jarvis/screenshots"
    )
    return d.expanduser()


def _save_shot(png: bytes, shot_id: str) -> str:
    d = _screenshots_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{shot_id}.png"
    path.write_bytes(png)
    _prune_shots(d)
    return str(path)


def _prune_shots(d: Path, max_age_s: float = 24 * 3600) -> int:
    """Delete screenshots older than 24 h. Returns count removed."""
    now = time.time()
    removed = 0
    for p in d.glob("shot-*.png"):
        try:
            if now - p.stat().st_mtime > max_age_s:
                p.unlink()
                removed += 1
        except OSError:
            pass
    return removed
