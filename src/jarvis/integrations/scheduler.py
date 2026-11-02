"""Cron-like scheduler (Master Plan Task 6.4, part 2).

Design decision: a tiny in-house cron parser instead of APScheduler —
zero new dependencies, deterministic in tests, and the feature set we
need (cron specs, one-shot, intervals, file-watch) is small.

SAFETY (plan-mandated): a scheduled job may **auto-execute READ tools
only**. If the job's tool resolves above READ, the scheduler does NOT
run it — it emits a notification asking the user to confirm instead.
Silent destructive execution from a timer is never allowed.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from jarvis.tools.registry import Risk, resolve

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cron parsing (minute hour dom month dow, * and */n and lists/ranges)
# ---------------------------------------------------------------------------

def _parse_field(text: str, lo: int, hi: int) -> set:
    values: set = set()

    def add(v: int) -> None:
        if lo <= v <= hi:
            values.add(v)

    for part in text.split(","):
        part = part.strip()
        if part == "*":
            values.update(range(lo, hi + 1))
        elif part.startswith("*/"):
            step = int(part[2:])
            values.update(range(lo, hi + 1, step))
        elif "-" in part:
            a, b = part.split("-", 1)
            step = 1
            if "/" in b:
                b, s = b.split("/", 1)
                step = int(s)
            values.update(range(int(a), int(b) + 1, step))
        else:
            add(int(part))
    return values


@dataclass(frozen=True)
class CronSpec:
    minute: str = "*"
    hour: str = "*"
    dom: str = "*"
    month: str = "*"
    dow: str = "*"

    def matches(self, dt: datetime) -> bool:
        return _cron_matches(self, dt)

    @staticmethod
    def parse(spec: str) -> "CronSpec":
        parts = spec.split()
        if len(parts) != 5:
            raise ValueError(f"cron spec needs 5 fields, got {len(parts)}: {spec!r}")
        return CronSpec(*parts)


def _cron_matches(spec: CronSpec, dt: datetime) -> bool:
    minutes = _parse_field(spec.minute, 0, 59)
    hours = _parse_field(spec.hour, 0, 23)
    doms = _parse_field(spec.dom, 1, 31)
    months = _parse_field(spec.month, 1, 12)
    # dow: accept 0-7, normalize 7 -> 0
    dows_raw = _parse_field(spec.dow, 0, 7)
    dows = {0 if d == 7 else d for d in dows_raw}
    # Standard cron day semantics: when dom is "*", dow decides; when dow
    # is "*", dom decides; when both are restricted, either may match.
    dom_star = spec.dom.strip() == "*"
    dow_star = spec.dow.strip() == "*"
    if dom_star and dow_star:
        day_ok = True
    elif dom_star:
        day_ok = (dt.isoweekday() % 7) in dows
    elif dow_star:
        day_ok = dt.day in doms
    else:
        day_ok = (dt.day in doms) or ((dt.isoweekday() % 7) in dows)
    return (dt.minute in minutes and dt.hour in hours
            and dt.month in months and day_ok)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@dataclass
class Job:
    id: str
    name: str
    tool: str
    args: Dict[str, Any] = field(default_factory=dict)
    cron: Optional[str] = None          # "*/30 * * * *"
    every_s: Optional[float] = None     # interval
    at: Optional[datetime] = None       # one-shot
    watch_file: Optional[str] = None    # file-watch trigger
    enabled: bool = True
    last_run: Optional[datetime] = None
    last_file_hash: Optional[str] = None

    def due(self, now: datetime) -> bool:
        if not self.enabled:
            return False
        if self.cron:
            if self.last_run and (now - self.last_run) < timedelta(minutes=1):
                return False  # fire at most once per minute per cron job
            return _cron_matches(CronSpec.parse(self.cron), now)
        if self.every_s:
            if self.last_run is None:
                return True
            return (now - self.last_run).total_seconds() >= self.every_s
        if self.at:
            return self.last_run is None and now >= self.at
        return False


@dataclass
class Notification:
    """A proactive nudge for the user (never a silent action)."""
    title: str
    body: str
    source: str          # "heartbeat" | "scheduler" | ...
    urgency: str = "normal"   # "low" | "normal" | "urgent"


class Scheduler:
    """Runs jobs on the BACKGROUND lane. READ-only tools auto-execute;
    anything above READ becomes a Notification instead."""

    def __init__(self,
                 notify: Callable[[Notification], None],
                 tick_s: float = 20.0) -> None:
        self._jobs: Dict[str, Job] = {}
        self._notify = notify
        self._tick_s = tick_s
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # -- job management ------------------------------------------------
    def add_job(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job

    def remove_job(self, job_id: str) -> bool:
        with self._lock:
            return self._jobs.pop(job_id, None) is not None

    def list_jobs(self) -> List[Job]:
        with self._lock:
            return list(self._jobs.values())

    # -- lifecycle ------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="jarvis-scheduler")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.wait(self._tick_s):
            try:
                self.tick(datetime.now())
            except Exception as e:
                logger.exception(f"scheduler tick failed: {e}")

    def tick(self, now: datetime) -> None:
        """Check all jobs once (public for tests)."""
        with self._lock:
            jobs = list(self._jobs.values())
        for job in jobs:
            try:
                if job.watch_file:
                    self._check_watch(job)
                elif job.due(now):
                    self._fire(job, now)
            except Exception as e:
                logger.exception(f"job {job.id} failed: {e}")

    # -- firing ---------------------------------------------------------
    def _check_watch(self, job: Job) -> None:
        path = job.watch_file or ""
        try:
            with open(path, "rb") as f:
                digest = hashlib.sha256(f.read()).hexdigest()
        except OSError:
            return
        if job.last_file_hash is None:
            job.last_file_hash = digest
            return
        if digest != job.last_file_hash:
            job.last_file_hash = digest
            self._fire(job, datetime.now())

    def _fire(self, job: Job, now: datetime) -> None:
        job.last_run = now
        spec = resolve(job.tool, job.args)
        if spec is None:
            self._notify(Notification(
                title=f"Scheduled job failed: {job.name}",
                body=f"Unknown tool: {job.tool}",
                source="scheduler", urgency="low"))
            return
        if spec.risk > Risk.READ:
            # SAFETY: never silently run above-READ from a timer.
            self._notify(Notification(
                title=f"Scheduled: {job.name}",
                body=(f"Wants to run {job.tool} ({spec.risk.name}). "
                      f"Confirm to execute — timers never run this silently."),
                source="scheduler", urgency="normal"))
            logger.info(f"job {job.id}: {job.tool} above READ -> notification")
            return
        from jarvis.tools.actions import run_action
        verdict, result = run_action(job.tool, job.args)
        logger.info(f"job {job.id}: {job.tool} -> {verdict}")
        if verdict != "allow":
            self._notify(Notification(
                title=f"Scheduled job needs attention: {job.name}",
                body=result[:300], source="scheduler", urgency="low"))
