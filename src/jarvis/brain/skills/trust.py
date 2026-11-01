"""Skill trust model (Task 4.6.3).

* LOCAL skills (shipped in the repo's skills/ dir): trusted by user action
  (they arrived with an explicit user-approved change).
* THIRD_PARTY skills (dropped into the skills dir by the user): hash-pinned
  on first load; all tools default to DESTRUCTIVE risk; never auto-installed
  from the internet; the source path is always shown.
* Risk override rule: the user may RAISE a tool's risk tier, never lower it
  without an explicit per-tool confirmation.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TrustLevel(str, Enum):
    LOCAL = "local"
    THIRD_PARTY = "third_party"


@dataclass
class SkillTrust:
    name: str
    level: TrustLevel
    source_path: str
    sha256: str = ""


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    targets = [path] if path.is_file() else sorted(path.rglob("*"))
    for child in targets:
        if child.is_file():
            h.update(child.name.encode())
            h.update(child.read_bytes())
    return h.hexdigest()


class TrustStore:
    """Remembers pins for third-party skills (path -> sha256)."""

    def __init__(self) -> None:
        self._pins: Dict[str, str] = {}

    def pin(self, name: str, digest: str) -> None:
        self._pins[name] = digest

    def check(self, name: str, digest: str) -> bool:
        """True if the skill is unchanged since pinning (or never pinned)."""
        pinned = self._pins.get(name)
        if pinned is None:
            return True
        return pinned == digest
