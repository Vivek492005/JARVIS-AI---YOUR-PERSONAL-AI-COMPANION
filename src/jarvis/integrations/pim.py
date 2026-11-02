"""Calendar / Mail / Tasks integrations (Master Plan Task 6.3).

Rules (from the plan):
* **Read-first.** Listing/reading is READ; creating calendar events and
  task items is REVERSIBLE; deleting events and *sending* mail is
  DESTRUCTIVE (send additionally needs an explicit confirmation with a
  full recipient+body preview — the policy gate asks, the handler
  embeds the preview in the prompt).
* Mail bodies are **untrusted** (injection!): tools that return them are
  marked ``carries_external_data`` so results enter prompts wrapped in
  ``<untrusted_data>``.
* Credentials: Google providers read OAuth tokens via
  :mod:`jarvis.core.secrets` (env/keyring). See
  ``docs/INTEGRATIONS_SETUP.md``. **Never hardcode.**

Providers are protocols; :func:`get_calendar`, :func:`get_mail` and
:func:`get_tasks` return the configured provider, defaulting to in-memory
fakes (safe on machines without accounts). A ``google`` provider is
registered when its optional deps import cleanly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class CalEvent:
    id: str
    title: str
    start: str          # ISO-8601
    end: str
    location: str = ""
    description: str = ""


@dataclass
class MailMsg:
    id: str
    sender: str
    subject: str
    snippet: str
    body: str = ""
    unread: bool = True


@dataclass
class TaskItem:
    id: str
    title: str
    done: bool = False
    due: str = ""


# ---------------------------------------------------------------------------
# Provider protocols
# ---------------------------------------------------------------------------

class CalendarProvider(Protocol):
    def list_events(self, start: str, end: str) -> List[CalEvent]: ...
    def create_event(self, title: str, start: str, end: str,
                     location: str = "", description: str = "") -> CalEvent: ...
    def delete_event(self, event_id: str) -> bool: ...


class MailProvider(Protocol):
    def list_messages(self, query: str = "", max_n: int = 10) -> List[MailMsg]: ...
    def read_message(self, msg_id: str) -> Optional[MailMsg]: ...
    def draft_message(self, to: str, subject: str, body: str) -> str: ...
    def send_message(self, to: str, subject: str, body: str) -> str: ...


class TaskProvider(Protocol):
    def list_tasks(self, include_done: bool = False) -> List[TaskItem]: ...
    def add_task(self, title: str, due: str = "") -> TaskItem: ...
    def complete_task(self, task_id: str) -> bool: ...


# ---------------------------------------------------------------------------
# Fake providers (default; also used by tests)
# ---------------------------------------------------------------------------

class FakeCalendar(CalendarProvider):
    def __init__(self) -> None:
        self._events: Dict[str, CalEvent] = {}
        self._n = 0

    def list_events(self, start: str, end: str) -> List[CalEvent]:
        return [e for e in self._events.values()
                if start <= e.start <= end]

    def create_event(self, title: str, start: str, end: str,
                     location: str = "", description: str = "") -> CalEvent:
        self._n += 1
        ev = CalEvent(id=f"ev{self._n}", title=title, start=start,
                      end=end, location=location, description=description)
        self._events[ev.id] = ev
        return ev

    def delete_event(self, event_id: str) -> bool:
        return self._events.pop(event_id, None) is not None


class FakeMail(MailProvider):
    def __init__(self) -> None:
        self._msgs: Dict[str, MailMsg] = {}
        self._drafts: List[Dict[str, str]] = []
        self._sent: List[Dict[str, str]] = []
        self._n = 0

    def seed(self, sender: str, subject: str, body: str,
             unread: bool = True) -> MailMsg:
        self._n += 1
        m = MailMsg(id=f"m{self._n}", sender=sender, subject=subject,
                    snippet=body[:80], body=body, unread=unread)
        self._msgs[m.id] = m
        return m

    def list_messages(self, query: str = "", max_n: int = 10) -> List[MailMsg]:
        q = query.lower()
        out = [m for m in self._msgs.values()
               if not q or q in m.subject.lower() or q in m.sender.lower()]
        return out[:max_n]

    def read_message(self, msg_id: str) -> Optional[MailMsg]:
        return self._msgs.get(msg_id)

    def draft_message(self, to: str, subject: str, body: str) -> str:
        self._drafts.append({"to": to, "subject": subject, "body": body})
        return f"draft-{len(self._drafts)}"

    def send_message(self, to: str, subject: str, body: str) -> str:
        self._sent.append({"to": to, "subject": subject, "body": body})
        return f"sent-{len(self._sent)}"


class FakeTasks(TaskProvider):
    def __init__(self) -> None:
        self._tasks: Dict[str, TaskItem] = {}
        self._n = 0

    def list_tasks(self, include_done: bool = False) -> List[TaskItem]:
        return [t for t in self._tasks.values()
                if include_done or not t.done]

    def add_task(self, title: str, due: str = "") -> TaskItem:
        self._n += 1
        t = TaskItem(id=f"t{self._n}", title=title, due=due)
        self._tasks[t.id] = t
        return t

    def complete_task(self, task_id: str) -> bool:
        t = self._tasks.get(task_id)
        if t is None:
            return False
        t.done = True
        return True


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

_cal: Optional[CalendarProvider] = None
_mail: Optional[MailProvider] = None
_tasks: Optional[TaskProvider] = None


def _provider_kind() -> str:
    from jarvis.core.secrets import get_secret
    # Explicit opt-in only: a real account is never used by accident.
    if get_secret("JARVIS_PIM_PROVIDER") == "google":
        return "google"
    return "fake"


def get_calendar() -> CalendarProvider:
    global _cal
    if _cal is None:
        _cal = _google_calendar() if _provider_kind() == "google" else FakeCalendar()
    return _cal


def get_mail() -> MailProvider:
    global _mail
    if _mail is None:
        _mail = _google_mail() if _provider_kind() == "google" else FakeMail()
    return _mail


def get_tasks() -> TaskProvider:
    global _tasks
    if _tasks is None:
        _tasks = _google_tasks() if _provider_kind() == "google" else FakeTasks()
    return _tasks


def reset_providers() -> None:
    """Tests only: drop cached providers."""
    global _cal, _mail, _tasks
    _cal, _mail, _tasks = None, None, None


def _google_calendar() -> CalendarProvider:
    from jarvis.integrations.google_pim import GoogleCalendar  # lazy
    return GoogleCalendar()


def _google_mail() -> MailProvider:
    from jarvis.integrations.google_pim import GoogleMail  # lazy
    return GoogleMail()


def _google_tasks() -> TaskProvider:
    from jarvis.integrations.google_pim import GoogleTasks  # lazy
    return GoogleTasks()


# ---------------------------------------------------------------------------
# Formatting helpers (keep tool outputs small and readable)
# ---------------------------------------------------------------------------

def _fmt_event(e: CalEvent) -> str:
    loc = f" @ {e.location}" if e.location else ""
    return f"[{e.id}] {e.title} | {e.start} -> {e.end}{loc}"


def _fmt_mail(m: MailMsg) -> str:
    flag = "*" if m.unread else " "
    return f"{flag}[{m.id}] {m.sender} — {m.subject}"
