"""Local latency metrics (Master Plan Task 2.7.3).

Every utterance turn appends one row to ``metrics/YYYY-MM-DD.csv`` —
local only, never uploaded — so latency regressions are visible over
time. Location: the per-install data dir (``%APPDATA%/jarvis`` on
Windows, ``~/.jarvis`` elsewhere), *not* the repo, to keep checkouts
clean.
"""

from __future__ import annotations

import csv
import logging
import os
import threading
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_CSV_FIELDS = [
    "ts",
    "trace",
    "path",
    "reflex_match_ms",
    "run_ms",
    "total_ms",
    "provider",
    "degraded",
    "error",
]


def _metrics_dir() -> str:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "jarvis", "metrics")
    else:
        d = os.path.join(os.path.expanduser("~"), ".jarvis", "metrics")
    os.makedirs(d, exist_ok=True)
    return d


class MetricsRecorder:
    """Thread-safe appender for the daily metrics CSV."""

    def __init__(self, metrics_dir: Optional[str] = None) -> None:
        self._dir = metrics_dir or _metrics_dir()
        os.makedirs(self._dir, exist_ok=True)
        self._lock = threading.Lock()

    def _path_for_today(self) -> str:
        day = time.strftime("%Y-%m-%d")
        return os.path.join(self._dir, f"{day}.csv")

    def record(
        self,
        trace: str,
        path: str,
        timings: Optional[Dict[str, float]] = None,
        provider: str = "",
        degraded: bool = False,
        error: str = "",
    ) -> None:
        """Append one utterance row. Never raises (metrics must not break
        the turn)."""
        timings = timings or {}
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "trace": trace,
            "path": path,  # "reflex" | "llm"
            "reflex_match_ms": f"{timings.get('reflex_match', 0.0):.1f}",
            "run_ms": f"{timings.get('run', 0.0):.1f}",
            "total_ms": f"{timings.get('total', 0.0):.1f}",
            "provider": provider,
            "degraded": "1" if degraded else "0",
            "error": error[:200],
        }
        try:
            with self._lock:
                path_csv = self._path_for_today()
                new = not os.path.exists(path_csv)
                with open(path_csv, "a", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
                    if new:
                        w.writeheader()
                    w.writerow(row)
        except OSError:
            logger.warning("could not write metrics row", exc_info=True)

    def tail(self, n: int = 20) -> list:
        """Last ``n`` rows of today's CSV (for ``jarvis doctor``)."""
        try:
            with open(self._path_for_today(), encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            return rows[-n:]
        except (OSError, ValueError):
            return []
