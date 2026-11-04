"""VLM fallback — set-of-marks (Master Plan Task 5.4).

Last-resort rung (reliability ★☆☆☆☆): when UIA/DOM fail, take a
screenshot, overlay **numbered boxes** on candidate clickable regions
(from the UIA tree / OCR), and ask the VLM "kaunsa number?". Guards:

- **Cost/latency guard:** max 3 VLM calls per task.
- **Verify loop:** after a click, re-capture and run ``verify_fn``;
  fail -> retry (max 2) -> handoff.
- **Handoff triggers:** login form, CAPTCHA, payment, 2FA, UAC prompt ->
  "Mujhse nahi hoga, aap kar do." (never try to defeat them).
- **VLM output is untrusted:** only the integer mark index is used;
  free-form instructions from the VLM are ignored.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from jarvis.perception import backends as _backends
from jarvis.perception.backends import ElementNode
from jarvis.perception.privacy import check_window
from jarvis.perception.screen import ScreenCapture, get_shot

logger = logging.getLogger(__name__)

MAX_VLM_CALLS_PER_TASK = 3
MAX_CLICK_RETRIES = 2

# Prompts mentioning these hand off to the user immediately.
HANDOFF_PATTERNS = (
    "login",
    "log in",
    "sign in",
    "password",
    "captcha",
    "2fa",
    "two-factor",
    "otp",
    "payment",
    "pay ",
    "checkout",
    "card number",
    "uac",
    "user account control",
    "administrator permission",
)

HANDOFF_MESSAGE = "Mujhse nahi hoga, aap kar do — yeh login/CAPTCHA/payment jaisa step hai."


class HandoffRequired(Exception):
    """The task needs the human (login/CAPTCHA/payment/2FA/UAC or VLM limits)."""


@dataclass
class Mark:
    index: int  # 1-based, shown on the overlay
    element_id: str
    bounds: Tuple[int, int, int, int]
    label: str


def _handoff_triggered(prompt: str) -> bool:
    lowered = (prompt or "").lower()
    return any(p in lowered for p in HANDOFF_PATTERNS)


def build_marks(handle: Optional[int] = None, max_marks: int = 12) -> Tuple[List[Mark], int]:
    """Candidate clickable regions from the UIA tree.

    Returns (marks, handle). Elements with empty bounds are skipped.
    """
    uia = _backends.get_backend("uia")
    if handle is None:
        ctx = _backends.get_backend("context")
        win = ctx.active_window()
        handle = win.handle
        check_window(win.title, win.process)
    tree = uia.get_tree(handle, depth=4)
    marks: List[Mark] = []

    def walk(node: ElementNode) -> None:
        if len(marks) >= max_marks:
            return
        x, y, w, h = node.bounds
        if (
            node.role in ("button", "link", "menuitem", "checkbox", "radiobutton", "tabitem")
            and w > 0
            and h > 0
            and node.enabled
        ):
            marks.append(
                Mark(
                    index=len(marks) + 1,
                    element_id=node.element_id,
                    bounds=(x, y, w, h),
                    label=node.name,
                )
            )
        for child in node.children:
            walk(child)

    walk(tree)
    return marks, handle


def overlay_marks(png: bytes, marks: List[Mark]) -> bytes:
    """Draw numbered boxes on the screenshot. Falls back to the raw PNG
    when PIL is unavailable (headless test envs)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.warning("PIL missing; returning unmarked screenshot")
        return png
    img = Image.open(io.BytesIO(png)).convert("RGB")
    draw = ImageDraw.Draw(img)
    for m in marks:
        x, y, w, h = m.bounds
        draw.rectangle([x, y, x + w, y + h], outline=(0, 255, 0), width=2)
        draw.rectangle([x, y - 14, x + 22, y], fill=(0, 255, 0))
        draw.text((x + 4, y - 13), str(m.index), fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class VLMClicker:
    """Set-of-marks click loop with guards."""

    def __init__(
        self,
        vlm_backend=None,
        max_calls: int = MAX_VLM_CALLS_PER_TASK,
        max_retries: int = MAX_CLICK_RETRIES,
    ) -> None:
        self._vlm = vlm_backend
        self.max_calls = max_calls
        self.max_retries = max_retries
        self.calls_made = 0

    def _vlm_be(self):
        return self._vlm or _backends.get_backend("vlm")

    def click_target(
        self,
        prompt: str,
        handle: Optional[int] = None,
        verify_fn: Optional[Callable[[], Tuple[bool, str]]] = None,
        max_marks: int = 12,
    ) -> str:
        """Click the element the VLM picks for ``prompt``.

        Raises :class:`HandoffRequired` on handoff triggers, VLM call
        budget exhaustion, or repeated verify failures.
        """
        if _handoff_triggered(prompt):
            raise HandoffRequired(HANDOFF_MESSAGE)
        cap = ScreenCapture()
        uia = _backends.get_backend("uia")

        last_why = "no attempt yet"
        for _ in range(1 + self.max_retries):
            if self.calls_made >= self.max_calls:
                raise HandoffRequired(
                    f"VLM call budget exhausted ({self.max_calls}/task). " + HANDOFF_MESSAGE
                )
            marks, used_handle = build_marks(handle, max_marks)
            if not marks:
                raise HandoffRequired("koi clickable element nahi mila. " + HANDOFF_MESSAGE)
            info = cap.capture(handle=used_handle)
            png = get_shot(str(info["shot_id"]))
            marked = overlay_marks(png or b"", marks)
            # VLM output is untrusted: ONLY the integer index is used.
            self.calls_made += 1
            try:
                idx = int(
                    self._vlm_be().pick_element(
                        marked,
                        f"Which numbered box matches: {prompt}? Reply with the number only.",
                        max_marks=len(marks),
                    )
                )
            except (TypeError, ValueError):
                last_why = "VLM did not return a number"
                continue
            if not 1 <= idx <= len(marks):
                last_why = f"VLM returned out-of-range index {idx}"
                continue
            mark = marks[idx - 1]
            if not uia.invoke(mark.element_id):
                last_why = f"invoke failed for {mark.element_id}"
                continue
            if verify_fn is None:
                return f"clicked '{mark.label}' (mark {idx}; unverified — no postcondition)"
            ok, evidence = verify_fn()
            if ok:
                return f"clicked '{mark.label}' (mark {idx}); verified: {evidence}"
            last_why = f"verify failed: {evidence}"
        raise HandoffRequired(f"VLM click failed after retries: {last_why}. " + HANDOFF_MESSAGE)
