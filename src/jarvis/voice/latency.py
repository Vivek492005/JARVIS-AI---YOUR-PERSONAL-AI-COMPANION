"""Latency budget + instrumentation (Master Plan Task 3.10).

Budget table (plan, p50):

| Stage                          | Target  |
|--------------------------------|---------|
| Speech end -> VAD end-of-turn  | <= 300 ms |
| STT final (streaming)          | <= 250 ms |
| LLM first token (fast tier)    | <= 400 ms |
| TTS first audio                | <= 250 ms |
| **Total (mic-off -> pehli awaaz)** | **<= 1.2-1.5 s** |
| Reflex path                    | <= 200 ms |

:py:class:`StageTimer` records per-stage timings into a turn's timing
dict (which :py:class:`jarvis.core.metrics.MetricsRecorder` persists);
:py:func:`latency_summary` reads recent metrics CSVs and reports p50 per
stage against the budget for ``jarvis doctor --latency``.
"""

from __future__ import annotations

import csv
import glob
import logging
import os
import statistics
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

# Stage name -> p50 budget in milliseconds.
BUDGET_MS: Dict[str, float] = {
    "vad_endpoint": 300.0,
    "stt_final": 250.0,
    "llm_first_token": 400.0,
    "tts_first_audio": 250.0,
    "total": 1500.0,
    "reflex": 200.0,
}


class StageTimer:
    """Collects per-stage timings for one turn."""

    def __init__(self) -> None:
        self.timings: Dict[str, float] = {}
        self._starts: Dict[str, float] = {}

    def start(self, stage: str) -> None:
        self._starts[stage] = time.monotonic()

    def stop(self, stage: str) -> float:
        t0 = self._starts.pop(stage, None)
        dt_ms = (time.monotonic() - t0) * 1000.0 if t0 else 0.0
        self.timings[stage] = self.timings.get(stage, 0.0) + dt_ms
        return dt_ms

    @contextmanager
    def time(self, stage: str) -> Iterator[None]:
        self.start(stage)
        try:
            yield
        finally:
            self.stop(stage)

    def over_budget(self) -> Dict[str, float]:
        """Stages whose timing exceeds the budget (stage -> ms over)."""
        over = {}
        for stage, ms in self.timings.items():
            budget = BUDGET_MS.get(stage)
            if budget is not None and ms > budget:
                over[stage] = ms - budget
        return over


@dataclass
class LatencyReport:
    stage: str
    p50_ms: Optional[float]
    budget_ms: float
    n: int

    @property
    def status(self) -> str:
        if self.p50_ms is None:
            return "nodata"
        return "ok" if self.p50_ms <= self.budget_ms else "over"


def _stage_columns() -> Dict[str, str]:
    # metrics CSV column -> stage key
    return {
        "vad_endpoint_ms": "vad_endpoint",
        "stt_final_ms": "stt_final",
        "llm_first_token_ms": "llm_first_token",
        "tts_first_audio_ms": "tts_first_audio",
        "total_ms": "total",
        "reflex_match_ms": "reflex",
    }


def latency_summary(metrics_dir: str, days: int = 7) -> List[LatencyReport]:
    """p50 per stage over recent metrics CSVs vs the budget table."""
    colmap = _stage_columns()
    samples: Dict[str, List[float]] = {s: [] for s in colmap.values()}
    files = sorted(glob.glob(os.path.join(metrics_dir, "*.csv")))[-days:]
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    for col, stage in colmap.items():
                        v = (row.get(col) or "").strip()
                        try:
                            if v:
                                samples[stage].append(float(v))
                        except ValueError:
                            pass
        except OSError:
            logger.warning(f"could not read metrics {path}")
    reports = []
    for stage, budget in BUDGET_MS.items():
        vals = samples.get(stage, [])
        reports.append(LatencyReport(
            stage=stage,
            p50_ms=round(statistics.median(vals), 1) if vals else None,
            budget_ms=budget, n=len(vals)))
    return reports


def format_latency_report(reports: List[LatencyReport]) -> str:
    lines = ["latency budget (p50):"]
    for r in reports:
        if r.status == "nodata":
            lines.append(f"  {r.stage:<16} no data (budget {r.budget_ms:.0f} ms)")
        else:
            mark = "OK  " if r.status == "ok" else "OVER"
            lines.append(f"  {mark} {r.stage:<16} p50 {r.p50_ms:.0f} ms "
                         f"(budget {r.budget_ms:.0f} ms, n={r.n})")
    return "\n".join(lines)
