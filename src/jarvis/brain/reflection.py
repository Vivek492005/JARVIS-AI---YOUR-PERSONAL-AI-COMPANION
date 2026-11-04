"""Reflection / learning (Master Plan Task 4.8, P2 — careful).

After a failure, a short "lesson" (what failed, what to do instead) goes
into episodic memory. A weekly review job turns lessons into MEMORY.md
proposals — **with user approval** (never auto-written: poisoning/drift
risk, per the plan).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from jarvis.brain.memory.store import MemoryStore

logger = logging.getLogger(__name__)


@dataclass
class Lesson:
    what_failed: str
    what_to_do: str
    context: str = ""


_LESSON_RE = re.compile(r"(?i)(?:lesson|seekha|seekh)\s*:\s*(.+?)(?:\s*->\s*|\s*[;|]\s*)(.+)$")


def parse_lesson(text: str) -> Optional[Lesson]:
    """Parse 'lesson: X -> Y' / 'seekha: X -> Y' into a Lesson."""
    m = _LESSON_RE.search((text or "").strip())
    if not m:
        return None
    return Lesson(what_failed=m.group(1).strip(), what_to_do=m.group(2).strip())


class Reflector:
    """Records lessons and builds weekly MEMORY.md proposals."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def record_failure(self, tool: str, evidence: str, lesson_text: str = "") -> Optional[int]:
        """Store a failure episode + optional lesson. Returns lesson ep id."""
        self.store.add_episode("system", f"FAILED: {tool}: {evidence}", tool=tool, outcome="failed")
        lesson = parse_lesson(lesson_text)
        if lesson is None:
            return None
        eid = self.store.add_episode(
            "system",
            f"LESSON: {lesson.what_failed} -> {lesson.what_to_do}",
            tool=tool,
            outcome="lesson",
        )
        logger.info("recorded lesson for %s", tool)
        return eid

    def weekly_proposals(self, limit: int = 50) -> List[str]:
        """Turn recent LESSON episodes into MEMORY.md proposal lines.

        Returns proposal strings; the caller must get user approval before
        appending (ProfileStore.append_approved).
        """
        proposals = []
        seen = set()
        for ep in self.store.recent_episodes(limit):
            text = ep["text"] or ""
            if not text.startswith("LESSON:"):
                continue
            body = text[len("LESSON:") :].strip()
            if body and body not in seen:
                seen.add(body)
                proposals.append(f"Seekha gaya: {body}")
        return proposals
