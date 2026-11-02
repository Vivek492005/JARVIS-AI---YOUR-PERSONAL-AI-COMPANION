"""Heartbeat & proactivity (Master Plan Task 6.4, part 1).

Every ~30 minutes JARVIS wakes up, runs a READ-only checklist, and stays
silent (``HEARTBEAT_OK``) unless something needs the user. Anything that
isn't a read becomes a :class:`Notification`, never a silent action.

Rules enforced here:
* **READ-only auto.** Heartbeat checks call tools through
  :func:`run_action`; any check whose tool resolves above READ is
  skipped (logged) — a heartbeat must never confirm-gate or execute.
* **Quiet hours** (default 23:00–07:00): silent except ``urgent``
  (battery critical).
* **Rate limit**: max ``max_per_day`` proactive notifications (default
  20); per-rule opt-in flags.
* **Budget guard**: no LLM calls on the heartbeat path — checks use
  tools directly (or the reflex router). The heartbeat never spends
  model budget.
* **Daily Brief** is opt-in (``daily_brief: true``): calendar + tasks +
  top unread mail, spoken once in the morning.

The default checklist mirrors the plan's ``HEARTBEAT.md``; a custom file
can override it (``checklist_path``), one ``- [ ]`` rule per line —
unknown rules are ignored, never executed as code.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, time as dtime
from typing import Any, Callable, Dict, List, Optional

from jarvis.integrations.scheduler import Notification
from jarvis.tools.registry import Risk, resolve

logger = logging.getLogger(__name__)

DEFAULT_CHECKLIST = """# Heartbeat (har 30 min; quiet hours 23:00-07:00)
- [ ] Calendar: agle 30 min mein meeting? -> bolo
- [ ] Gmail: VIP senders se unread? -> short summary
- [ ] Battery < 15% aur unplugged? -> warn
Agar kuch nahi: HEARTBEAT_OK (chup raho)
"""

QUIET_START = dtime(23, 0)
QUIET_END = dtime(7, 0)


def in_quiet_hours(now: datetime,
                   start: dtime = QUIET_START,
                   end: dtime = QUIET_END) -> bool:
    t = now.time()
    if start <= end:
        return start <= t < end
    return t >= start or t < end  # overnight window


@dataclass
class HeartbeatConfig:
    interval_s: float = 1800.0
    quiet_start: dtime = QUIET_START
    quiet_end: dtime = QUIET_END
    max_per_day: int = 20
    # per-rule opt-in; unknown rules default to False (opt-in, not opt-out)
    rules: Dict[str, bool] = field(default_factory=lambda: {
        "calendar_meeting": True,
        "mail_vip": True,
        "battery_low": True,
        "daily_brief": False,
    })
    vip_senders: List[str] = field(default_factory=list)
    checklist_path: Optional[str] = None


class Heartbeat:
    def __init__(self,
                 config: Optional[HeartbeatConfig] = None,
                 notify: Optional[Callable[[Notification], None]] = None,
                 now_fn: Callable[[], datetime] = datetime.now) -> None:
        self.config = config or HeartbeatConfig()
        self._notify = notify or (lambda n: logger.info(
            f"heartbeat notify [{n.urgency}] {n.title}: {n.body}"))
        self._now = now_fn
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._sent_today: List[datetime] = []
        self._lock = threading.Lock()
        self._brief_done_for: Optional[str] = None  # date string

    # -- lifecycle ------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="jarvis-heartbeat")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.wait(self.config.interval_s):
            try:
                self.tick()
            except Exception as e:
                logger.exception(f"heartbeat tick failed: {e}")

    # -- one cycle -------------------------------------------------------
    def tick(self) -> str:
        """Run one heartbeat cycle. Returns 'HEARTBEAT_OK' or 'NOTIFIED'."""
        now = self._now()
        self._prune_counts(now)
        notes: List[Notification] = []
        notes += self._check_calendar(now)
        notes += self._check_mail(now)
        notes += self._check_battery(now)
        notes += self._check_daily_brief(now)

        if not notes:
            logger.debug("HEARTBEAT_OK")
            return "HEARTBEAT_OK"

        quiet = in_quiet_hours(now, self.config.quiet_start,
                               self.config.quiet_end)
        sent_any = False
        for n in notes:
            if quiet and n.urgency != "urgent":
                logger.info(f"heartbeat: quiet hours, holding [{n.title}]")
                continue
            if not self._within_budget():
                logger.warning("heartbeat: daily notification budget "
                               "exhausted, holding remainder")
                break
            self._notify(n)
            with self._lock:
                self._sent_today.append(now)
            sent_any = True
        return "NOTIFIED" if sent_any else "HEARTBEAT_OK"

    def _prune_counts(self, now: datetime) -> None:
        with self._lock:
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
            self._sent_today = [t for t in self._sent_today if t >= cutoff]

    def _within_budget(self) -> bool:
        with self._lock:
            return len(self._sent_today) < self.config.max_per_day

    def _rule_on(self, name: str) -> bool:
        return bool(self.config.rules.get(name, False))

    # -- checks (READ-only; anything else is skipped, never executed) ----
    def _run_read(self, tool: str, args: Dict[str, Any]) -> Optional[str]:
        from jarvis.tools.actions import run_action
        spec = resolve(tool, args)
        if spec is None or spec.risk > Risk.READ:
            logger.warning(f"heartbeat: refusing non-READ tool {tool}")
            return None
        verdict, result = run_action(tool, args)
        if verdict != "allow":
            return None
        return result

    def _check_calendar(self, now: datetime) -> List[Notification]:
        if not self._rule_on("calendar_meeting"):
            return []
        from datetime import timedelta
        start = now.isoformat()
        end = (now + timedelta(minutes=30)).isoformat()
        result = self._run_read("calendar_list",
                                {"start": start, "end": end})
        if not result or result.strip() in ("", "No events.", "[]"):
            return []
        return [Notification(
            title="Meeting in 30 minutes",
            body=result[:400], source="heartbeat", urgency="normal")]

    def _check_mail(self, now: datetime) -> List[Notification]:
        if not self._rule_on("mail_vip") or not self.config.vip_senders:
            return []
        result = self._run_read("mail_list", {"query": "is:unread",
                                              "max_n": 10})
        if not result:
            return []
        vips = [line for line in result.splitlines()
                if any(v.lower() in line.lower()
                       for v in self.config.vip_senders)]
        if not vips:
            return []
        return [Notification(
            title=f"{len(vips)} unread from VIP senders",
            body="\n".join(vips)[:500], source="heartbeat",
            urgency="normal")]

    def _check_battery(self, now: datetime) -> List[Notification]:
        if not self._rule_on("battery_low"):
            return []
        result = self._run_read("system_control",
                                {"action": "check_battery"})
        if not result:
            return []
        low = "low" in result.lower() or "%" in result and _pct(result) < 15
        if low:
            return [Notification(
                title="Battery low",
                body=result[:200], source="heartbeat", urgency="urgent")]
        return []

    def _check_daily_brief(self, now: datetime) -> List[Notification]:
        if not self._rule_on("daily_brief"):
            return []
        today = now.date().isoformat()
        if self._brief_done_for == today:
            return []
        if now.hour < 6 or now.hour > 10:
            return []  # morning window only
        parts = []
        cal = self._run_read("calendar_list", {
            "start": now.isoformat(),
            "end": now.replace(hour=23, minute=59).isoformat()})
        if cal:
            parts.append("Today's calendar:\n" + cal[:600])
        tasks = self._run_read("tasks_list", {})
        if tasks:
            parts.append("Open tasks:\n" + tasks[:400])
        if not parts:
            return []
        self._brief_done_for = today
        return [Notification(
            title="Daily Brief",
            body="\n\n".join(parts)[:1200], source="heartbeat",
            urgency="normal")]


def _pct(text: str) -> int:
    import re
    m = re.search(r"(\d+)\s*%", text)
    return int(m.group(1)) if m else 100
