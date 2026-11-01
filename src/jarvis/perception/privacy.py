"""Privacy helpers for perception surfaces (Tasks 5.2/5.3/5.8).

Certain windows must never be described, captured, or OCR'd:
password managers, banking/finance, private browsing. Matching is
case-insensitive substring on window title + process name.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Tuple

# Substrings that mark a window as sensitive. Kept as plain substrings
# (not full regexes) so the list stays auditable; compiled below.
_SENSITIVE_SUBSTRINGS: Tuple[str, ...] = (
    # password managers
    "keepass", "1password", "bitwarden", "lastpass", "dashlane",
    "keepassxc", "enpass", "nordpass", "password manager",
    # banking / finance
    "bank", "banking", "paytm", "phonepe", "gpay", "upi",
    "zerodha", "groww", "upstox", "hdfc", "icici", "sbi ",
    "credit card", "netbanking", "net banking",
    # private browsing
    "incognito", "private browsing", "inprivate",
    # secrets
    "seed phrase", "recovery phrase", "private key",
)

_PATTERNS: List[re.Pattern] = [
    re.compile(re.escape(s), re.IGNORECASE) for s in _SENSITIVE_SUBSTRINGS
]


def is_sensitive_window(title: str = "", process: str = "") -> bool:
    """True if the window looks like a password manager, banking app,
    or private-browsing session — describe/capture must be refused."""
    haystack = f"{title or ''} {process or ''}"
    return any(p.search(haystack) for p in _PATTERNS)


def check_window(title: str = "", process: str = "") -> None:
    """Raise :class:`SensitiveWindowError` when the window is sensitive."""
    if is_sensitive_window(title, process):
        raise SensitiveWindowError(
            f"refused: window looks sensitive (title={title!r}, process={process!r})"
        )


class SensitiveWindowError(PermissionError):
    """Raised when a perception action targets a sensitive window."""


def redact_text(text: str, patterns: Iterable[str] = ()) -> str:
    """Best-effort redaction of card-like / secret-like runs in OCR text.

    Replaces 12-19 digit runs (card numbers) and ``password=...`` style
    assignments with ``[REDACTED]``. Not a substitute for the window
    blocklist — a second layer.
    """
    out = re.sub(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{1,4}\b",
                 "[REDACTED]", text)
    out = re.sub(r"(?i)(password|passwd|pwd|secret|token)\s*[:=]\s*\S+",
                 r"\1=[REDACTED]", out)
    for pat in patterns:
        out = out.replace(pat, "[REDACTED]")
    return out
