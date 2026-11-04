"""Turn-capture heuristics (whole-brain integration, Phase B).

After each conversation turn, :func:`extract_candidates` scans the USER's
message for durable personal facts worth remembering. Only the user's own
words are scanned — never tool outputs, file contents, or web content
(poisoning defense, same rule as write_policy).

Patterns (English + Hindi/Hinglish):
    - identity:  "my name is X", "mera naam X hai"
    - preference: "I like/prefer/love X", "mujhe X pasand hai"
    - fact:      "my <thing> is <value>", "meri <thing> <value> hai"
    - reminder:  "remind me to X", "yaad dilana X"
    - correction:"no, I meant X", "nahi, mera matlab X tha"  (high value)
    - event:     "my birthday is X", "mera birthday X ko hai"

Every candidate still passes through
:py:func:`~jarvis.brain.memory.write_policy.validate_write` before it is
saved, so sensitive content is blocked at the gate.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class Candidate:
    text: str
    importance: float = 0.6


# (pattern, importance, template)
_NAME_EN = r"(?i)\bmy name is\s+([A-Za-z][\w]*(?:\s+(?!and\b|or\b)[A-Za-z][\w]*){0,2})"
_NAME_HI = (
    r"(?i)\bmera naam\s+([A-Za-z\u0900-\u097F][\w\u0900-\u097F]*"
    r"(?:\s+(?!aur\b|or\b)[A-Za-z\u0900-\u097F][\w\u0900-\u097F]*){0,2})\s+hai\b"
)
_LIKE_EN = r"(?i)\bi (?:really |truly |just )?(like|love|prefer)\s+(.+?)(?:\.|$)"
_DISLIKE_EN = r"(?i)\bi (?:really |truly |just )?(hate|dislike)\s+(.+?)(?:\.|$)"
_MY_X_IS_Y = r"(?i)\bmy ((?!name\b)[\w ]{2,30}?)\s+is\s+(.+?)(?:\.|$)"
_MERI_X_HAI_Y = r"(?i)\bmer[ai]\s+([\w ]{2,30}?)\s+hai\s+(.+?)(?:\.|$)"
_PATTERNS = [
    # identity — names are 1-3 words; stop at conjunctions/punctuation
    (re.compile(_NAME_EN), 0.9, "User's name is {0}"),
    (re.compile(_NAME_HI), 0.9, "User's name is {0}"),
    # preferences
    (re.compile(_LIKE_EN, re.S), 0.7, "User {0}s {1}"),
    (re.compile(r"(?i)\bmujhe\s+(.+?)\s+pasand hai\b"), 0.7, "User likes {0}"),
    (re.compile(_DISLIKE_EN, re.S), 0.7, "User dislikes {1}"),
    (re.compile(r"(?i)\bmujhe\s+(.+?)\s+pasand nahi\b"), 0.7, "User dislikes {0}"),
    # my-X-is-Y facts (skip 'name' — the identity pattern owns it)
    (re.compile(_MY_X_IS_Y, re.S), 0.8, "User's {0} is {1}"),
    (re.compile(_MERI_X_HAI_Y, re.S), 0.8, "User's {0} is {1}"),
    # reminders
    (re.compile(r"(?i)\bremind me to\s+(.+?)(?:\.|$)", re.S), 0.75, "Reminder: {0}"),
    (re.compile(r"(?i)\byaad dila(?:na|o)\s+(.+?)(?:\.|$)", re.S), 0.75, "Reminder: {0}"),
    # corrections — the user fixing JARVIS is high-signal
    (re.compile(r"(?i)\bno,?\s+i meant\s+(.+?)(?:\.|$)", re.S), 0.85, "Correction: {0}"),
    (re.compile(r"(?i)\bnahi,?\s+mera matlab\s+(.+?)\s+tha\b"), 0.85, "Correction: {0}"),
    (re.compile(r"(?i)\bactually,?\s+(.+?)(?:\.|$)", re.S), 0.6, "Note: {0}"),
    # dates / events
    (re.compile(r"(?i)\bmy birthday is\s+(.+?)(?:\.|$)", re.S), 0.9, "User's birthday is {0}"),
    (re.compile(r"(?i)\bmera birthday\s+(.+?)\s+ko hai\b"), 0.9, "User's birthday is {0}"),
]


def _clean(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip().strip(".,;:!?")
    return s


def extract_candidates(user_text: str, max_candidates: int = 3) -> List[Candidate]:
    """Extract durable-fact candidates from the user's message.

    Returns at most ``max_candidates``; empty list when nothing matches.
    Never raises — capture must not break a turn.
    """
    try:
        text = (user_text or "").strip()
        if len(text) < 8:
            return []
        out: List[Candidate] = []
        seen = set()
        for pat, importance, template in _PATTERNS:
            for m in pat.finditer(text):
                groups = [_clean(g) for g in m.groups() if g]
                groups = [g for g in groups if g and len(g) < 120]
                if not groups:
                    continue
                try:
                    rendered = template.format(*groups)
                except IndexError:
                    continue
                key = rendered.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(Candidate(text=rendered, importance=importance))
                if len(out) >= max_candidates:
                    return out
        return out
    except Exception:
        logger.exception("capture extraction failed")
        return []
