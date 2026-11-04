"""Memory write policy (Task 4.4.2 + 4.4.5).

* Facts are written ONLY when (a) the user explicitly said so
  ("yaad rakhna ..."), or (b) JARVIS proposed it and the user confirmed.
  The ``source`` column enforces this at the DB level.
* Web/file content can NEVER be a direct write source (poisoning defense) —
  :func:`guard_write_source` rejects it.
* Sensitive categories (passwords, card/ID numbers, health info, OTPs) are
  never stored — regex blocklist in :func:`contains_sensitive`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# --- sensitive-category blocklist --------------------------------------
_SENSITIVE_PATTERNS = [
    # passwords / secrets in "key: value" or "key=value" form
    re.compile(r"(?i)\b(passw(or)?d|passwd|pwd|api[_-]?key|secret|token)\b\s*[:=]\s*\S+"),
    # card numbers: 13-19 digits with common separators
    re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    # Aadhaar-style 12-digit groups
    re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    # OTPs
    re.compile(r"(?i)\b(otp|one[- ]time)\b.{0,20}\b\d{4,8}\b"),
    # health markers
    re.compile(r"(?i)\b(diagnos(is|ed)|prescription|medical report|hiv|cancer|pregnant)\b"),
    # generic "my X number is ..." for ID-ish numbers
    re.compile(r"(?i)\b(ssn|pan|aadhaar|passport|license)\b.{0,30}\b[A-Z0-9]{6,}\b"),
]


def contains_sensitive(text: str) -> Optional[str]:
    """Return the matched category description, or None if clean."""
    for pat in _SENSITIVE_PATTERNS:
        if pat.search(text or ""):
            return f"blocked sensitive pattern: {pat.pattern[:40]}..."
    return None


# --- write-source guard -------------------------------------------------

# Sources that may never write to memory directly.
_BANNED_SOURCES = frozenset({"web", "file", "clipboard", "untrusted"})


def guard_write_source(source: str) -> None:
    """Raise ValueError if the source is not allowed to write memory."""
    if source in _BANNED_SOURCES:
        raise ValueError(
            f"memory write from {source!r} rejected: web/file content can "
            "never write memory directly (poisoning defense)"
        )


@dataclass
class WriteRequest:
    key: str
    value: str
    source: str  # 'user' | 'confirmed'
    importance: float = 0.5


def validate_write(req: WriteRequest) -> Optional[str]:
    """Return an error string, or None if the write is allowed."""
    if req.source not in ("user", "confirmed"):
        return f"bad source {req.source!r}: must be 'user' or 'confirmed'"
    try:
        guard_write_source(req.source)
    except ValueError as e:
        return str(e)
    hit = contains_sensitive(req.key + " " + req.value)
    if hit:
        return hit
    if not req.key.strip() or not req.value.strip():
        return "empty key or value"
    return None
