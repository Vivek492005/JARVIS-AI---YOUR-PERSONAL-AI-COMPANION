"""Context awareness, privacy-safe (Master Plan Task 5.8).

What JARVIS knows about "right now":
- active window title + process (redacted to "[sensitive window]" when
  the blocklist matches),
- whether text is selected / clipboard holds text (**presence flags**),
- selection or clipboard **content** only when explicitly asked
  ("is par...", "is error ka matlab?").

Guards:
- master toggle ``context.enabled`` (default on); off -> minimal snapshot.
- sensitive windows never leak titles.
- selection/clipboard text goes through redaction + is marked
  ``carries_external_data`` (untrusted, Task 1.5) — context text is an
  injection surface, so the blocklist filter applies before it reaches
  the prompt.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from jarvis.perception import backends as _backends
from jarvis.perception.privacy import is_sensitive_window, redact_text

logger = logging.getLogger(__name__)

_SENSITIVE_PLACEHOLDER = "[sensitive window]"


@dataclass
class ContextSnapshot:
    window_title: str
    window_process: str
    has_selection: bool
    has_clipboard_text: bool
    selection_text: str = ""  # only when explicitly requested
    clipboard_text: str = ""  # only when explicitly requested
    ts: float = 0.0


def _enabled() -> bool:
    try:
        from jarvis.core.config import get_settings

        return bool(getattr(get_settings().context, "enabled", True))
    except Exception:
        return True


def _ctx_backend():
    return _backends.get_backend("context")


def get_context(detail: str = "basic") -> ContextSnapshot:
    """Capture the current context snapshot.

    ``detail``: "basic" (presence flags only), "selection" (+ selected
    text), "clipboard" (+ clipboard text). Content is redacted and must
    be treated as untrusted by callers.
    """
    now = time.time()
    if not _enabled():
        return ContextSnapshot(
            window_title="",
            window_process="",
            has_selection=False,
            has_clipboard_text=False,
            ts=now,
        )
    backend = _ctx_backend()
    win = backend.active_window()
    sensitive = is_sensitive_window(win.title, win.process)
    title = _SENSITIVE_PLACEHOLDER if sensitive else (win.title or "")
    process = _SENSITIVE_PLACEHOLDER if sensitive else (win.process or "")

    selection = ""
    try:
        selection = backend.selected_text() or ""
    except Exception as e:
        logger.debug("selected-text read best-effort failed: %s", e)
    has_selection = bool(selection.strip())

    try:
        has_clip = bool(backend.clipboard_has_text())
    except Exception:
        has_clip = False

    snap = ContextSnapshot(
        window_title=title,
        window_process=process,
        has_selection=has_selection,
        has_clipboard_text=has_clip,
        ts=now,
    )
    if detail == "selection" and has_selection and not sensitive:
        snap.selection_text = redact_text(selection[:4000])
    elif detail == "clipboard" and has_clip and not sensitive:
        try:
            snap.clipboard_text = redact_text((backend.clipboard_text() or "")[:4000])
        except Exception as e:
            logger.debug(
                "best-effort failed: %s",
                e,
            )
    return snap


def format_snapshot(snap: ContextSnapshot) -> str:
    """One-block text for the prompt (already redacted)."""
    lines = [
        f"active window: {snap.window_title or '(none)'} [{snap.window_process or '?'}]",
        f"selection: {'yes' if snap.has_selection else 'no'}",
        f"clipboard text: {'yes' if snap.has_clipboard_text else 'no'}",
    ]
    if snap.selection_text:
        lines.append(f"selected text: {snap.selection_text[:1000]}")
    if snap.clipboard_text:
        lines.append(f"clipboard text: {snap.clipboard_text[:1000]}")
    return "\n".join(lines)
