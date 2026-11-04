"""Profile sync (whole-brain integration, Phase C).

Pulls the semantic :py:class:`~jarvis.brain.memory.provider.Profile` from
the memory provider and renders it as a prompt block for personalization.

The profile is cached and refreshed explicitly (on agent init and via
:meth:`ProfileSync.refresh`) — never on the hot path of a turn. When the
semantic backend is down, the last cached profile (or nothing) is used;
persona behavior never breaks.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from jarvis.brain.memory.provider import MemoryProvider, Profile

logger = logging.getLogger(__name__)


class ProfileSync:
    """Caches the semantic user profile for prompt personalization."""

    def __init__(self, provider: MemoryProvider) -> None:
        self.provider = provider
        self._cached: Optional[Profile] = None
        self._last_refresh: float = 0.0

    def refresh(self, max_age_s: float = 3600) -> Profile:
        """Refresh the cached profile unless it's fresh. Never raises."""
        now = time.time()
        if self._cached is not None and (now - self._last_refresh) < max_age_s:
            return self._cached
        try:
            self._cached = self.provider.profile()
            self._last_refresh = now
            logger.info("profile refreshed: %d facts", len(self._cached.facts))
        except Exception:
            logger.exception("profile refresh failed; keeping cache")
            if self._cached is None:
                self._cached = Profile()
        return self._cached

    def format_for_prompt(self) -> str:
        """Render the cached profile as a prompt block, or ''."""
        prof = self._cached
        if not prof or (not prof.summary and not prof.facts):
            return ""
        lines = ["What I know about the user:"]
        if prof.summary:
            lines.append(prof.summary.strip())
        for f in prof.facts[:10]:
            lines.append(f"- {f}")
        return "\n".join(lines)
