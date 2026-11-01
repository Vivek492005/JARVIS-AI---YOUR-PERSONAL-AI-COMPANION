"""Profile layer (Task 4.4): curated, human-editable Markdown memory.

``USER.md`` / ``MEMORY.md`` live in the workspace directory so the user can
read and edit them directly (OpenClaw-style). The nightly consolidation job
(consolidate.py) only *proposes* lines — the user approves before anything
is appended.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class ProfileStore:
    """Read/append access to the Markdown profile files."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.workspace / name

    def read(self, name: str = "MEMORY.md") -> str:
        p = self._path(name)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def propose_lines(self, lines: List[str]) -> List[str]:
        """Return lines formatted as a proposal block (not yet written)."""
        return ["## Proposed memory additions (pending approval)", *[f"- {l}" for l in lines]]

    def append_approved(self, lines: List[str], name: str = "MEMORY.md") -> None:
        """Append user-approved lines. Only call after explicit approval."""
        if not lines:
            return
        p = self._path(name)
        with p.open("a", encoding="utf-8") as f:
            for line in lines:
                f.write(f"\n- {line.strip()}\n")
        logger.info("appended %d approved lines to %s", len(lines), name)
