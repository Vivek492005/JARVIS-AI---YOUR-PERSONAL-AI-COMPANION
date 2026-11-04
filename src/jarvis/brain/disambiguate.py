"""Disambiguation & undo UX (Master Plan Task 4.9).

"Kaunsa? 1) report_final.pdf 2) report_v2.pdf" — the user answers with a
number ("2"), an ordinal word ("pehla wala", "dusra", "akhri"), and the
choice resolves. "wapas kar do" replays the undo journal (see loop.py).
"""

from __future__ import annotations

import re
from typing import List, Optional

_ORDINALS = {
    "pehla": 0,
    "pehle": 0,
    "pahla": 0,
    "first": 0,
    "dusra": 1,
    "doosra": 1,
    "dusre": 1,
    "second": 1,
    "teesra": 2,
    "third": 2,
    "chautha": 3,
    "fourth": 3,
    "akhri": -1,
    "aakhri": -1,
    "last": -1,
}


def format_options(question: str, options: List[str]) -> str:
    """Render a numbered-options question for the user."""
    lines = [question.strip() or "Kaunsa?"]
    for i, opt in enumerate(options, 1):
        lines.append(f"{i}) {opt}")
    return "\n".join(lines)


def parse_selection(text: str, n_options: int) -> Optional[int]:
    """Parse "2", "dusra", "pehla wala", "akhri" -> 0-based index or None."""
    if n_options <= 0:
        return None
    t = (text or "").strip().lower()
    m = re.search(r"\b(\d+)\b", t)
    if m:
        idx = int(m.group(1)) - 1
        return idx if 0 <= idx < n_options else None
    # ordinal words, optionally followed by wala/wali/wale
    for word, idx in _ORDINALS.items():
        if re.search(rf"\b{word}\b(\s*wala|\s*wali|\s*wale)?", t):
            return n_options - 1 if idx == -1 else (idx if idx < n_options else None)
    return None


_UNDO_RE = re.compile(r"(?i)^\s*(wapas kar do|undo( that| it)?|revert)\b")


def is_undo_request(text: str) -> bool:
    return bool(_UNDO_RE.match((text or "").strip()))
