"""Integration ToolSpecs (Master Plan Phase 6): PIM, MCP, scheduler, heartbeat.

Registration follows the Phase-5 pattern: :func:`register_integration_tools`
is idempotent and hooked into ``actions._register_tools()``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from jarvis.tools.registry import REGISTRY, Risk, ToolSpec
from jarvis.tools.registry import tool as _reg

# Top-level: pim has no import cycle back into tools.
from jarvis.integrations.pim import (
    get_calendar, get_mail, get_tasks, _fmt_event, _fmt_mail,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Params models
# ---------------------------------------------------------------------------

class _CalList(BaseModel):
    start: str = Field("", description="ISO-8601 start")
    end: str = Field("", description="ISO-8601 end")


class _CalCreate(BaseModel):
    title: str
    start: str = Field(description="ISO-8601 start")
    end: str = Field(description="ISO-8601 end")
    location: str = ""
    description: str = ""


class _CalDelete(BaseModel):
    event_id: str


class _MailList(BaseModel):
    query: str = ""
    max_n: int = Field(10, ge=1, le=50)


class _MailRead(BaseModel):
    msg_id: str


class _MailCompose(BaseModel):
    to: str
    subject: str
    body: str


class _TasksList(BaseModel):
    include_done: bool = False


class _TaskAdd(BaseModel):
    title: str
    due: str = ""


class _TaskDone(BaseModel):
    task_id: str


class _McpDiscover(BaseModel):
    server: str = Field("", description="server name from mcp_servers.toml; empty = all")


class _SchedAdd(BaseModel):
    name: str
    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)
    cron: str = ""
    every_s: float = 0.0
    at: str = ""  # ISO-8601 one-shot


class _SchedRemove(BaseModel):
    job_id: str


class _Empty(BaseModel):
    pass


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _h_cal_list(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    from jarvis.integrations.pim import get_calendar
    from datetime import datetime, timedelta
    now = datetime.now(timezone_utc())
    start = args.get("start") or now.isoformat()
    end = args.get("end") or (now + timedelta(days=1)).isoformat()
    events = get_calendar().list_events(start, end)
    if not events:
        return "No events."
    return "\n".join(_fmt_event(e) for e in events)


def timezone_utc():  # tiny helper to keep imports local
    from datetime import timezone
    return timezone.utc


def _h_cal_create(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    from jarvis.integrations.pim import get_calendar
    e = get_calendar().create_event(args["title"], args["start"], args["end"],
                                    args.get("location", ""),
                                    args.get("description", ""))
    return "Created: " + _fmt_event(e)


def _h_cal_delete(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    ok = get_calendar().delete_event(args["event_id"])
    return "Deleted." if ok else "Event not found."


def _h_mail_list(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    from jarvis.integrations.pim import get_mail
    msgs = get_mail().list_messages(args.get("query", ""),
                                    args.get("max_n", 10))
    if not msgs:
        return "No messages."
    return "\n".join(_fmt_mail(m) for m in msgs)


def _h_mail_read(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    m = get_mail().read_message(args["msg_id"])
    if m is None:
        return "Message not found."
    return (f"From: {m.sender}\nSubject: {m.subject}\n\n"
            f"<untrusted_data>\n{m.body[:5000]}\n</untrusted_data>")


def _h_mail_summarize(args: Dict[str, Any], _c: Any = None,
                      _r: str = "") -> str:
    m = get_mail().read_message(args["msg_id"])
    if m is None:
        return "Message not found."
    # Extractive, deterministic: first 3 non-empty lines. (An LLM pass
    # can refine this; the extract never sends anything anywhere.)
    lines = [ln.strip() for ln in m.body.splitlines() if ln.strip()][:3]
    return (f"From: {m.sender} | Subject: {m.subject}\nSummary: "
            + " ".join(lines)[:500])


def _h_mail_draft(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    did = get_mail().draft_message(args["to"], args["subject"], args["body"])
    return f"Draft saved ({did}). Not sent."


def _h_mail_send(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    # DESTRUCTIVE: the policy gate confirms with a full preview first.
    # This handler only runs after ALLOW.
    sid = get_mail().send_message(args["to"], args["subject"], args["body"])
    return f"Sent to {args['to']} ({sid})."


def _h_tasks_list(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    from jarvis.integrations.pim import get_tasks
    tasks = get_tasks().list_tasks(args.get("include_done", False))
    if not tasks:
        return "No open tasks."
    return "\n".join(f"[{'x' if t.done else ' '}] [{t.id}] {t.title}"
                     + (f" (due {t.due})" if t.due else "")
                     for t in tasks)


def _h_tasks_add(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    t = get_tasks().add_task(args["title"], args.get("due", ""))
    return f"Added task [{t.id}] {t.title}."


def _h_tasks_done(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    ok = get_tasks().complete_task(args["task_id"])
    return "Marked done." if ok else "Task not found."


def _h_mcp_servers(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    from jarvis.integrations.mcp import load_server_configs
    from jarvis.core.config import get_settings
    path = getattr(get_settings(), "mcp_servers_toml",
                   "mcp_servers.toml")
    try:
        cfgs = load_server_configs(path)
    except FileNotFoundError:
        return "No mcp_servers.toml configured."
    if not cfgs:
        return "No MCP servers enabled."
    return "\n".join(f"- {c.name} (default risk {c.default_risk})"
                     for c in cfgs)


def _h_mcp_discover(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    # SYSTEM tier: spawning server subprocesses is a setup action.
    from jarvis.integrations.mcp import (MCPClient, discover_tools,
                                         load_server_configs,
                                         register_mcp_tools)
    from jarvis.core.config import get_settings
    path = getattr(get_settings(), "mcp_servers_toml",
                   "mcp_servers.toml")
    only = args.get("server", "")
    try:
        cfgs = load_server_configs(path)
    except FileNotFoundError:
        return "No mcp_servers.toml configured."
    found: List[str] = []
    for cfg in cfgs:
        if only and cfg.name != only:
            continue
        try:
            with MCPClient(cfg) as client:
                specs = discover_tools(client)
            register_mcp_tools(specs)
            found.extend(s.name for s in specs)
        except Exception as e:
            logger.warning(f"mcp discover {cfg.name} failed: {e}")
            found.append(f"{cfg.name}: FAILED ({e})")
    return "Discovered:\n" + "\n".join(f"- {n}" for n in found) \
        if found else "Nothing discovered."


def _h_heartbeat_now(args: Dict[str, Any], _c: Any = None,
                     _r: str = "") -> str:
    from jarvis.integrations.heartbeat import Heartbeat
    hb = Heartbeat(notify=lambda n: None)
    return hb.tick()


def _h_sched_list(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    sched = _get_scheduler()
    jobs = sched.list_jobs()
    if not jobs:
        return "No scheduled jobs."
    return "\n".join(f"- [{j.id}] {j.name} ({j.tool})"
                     for j in jobs)


def _h_sched_add(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    import uuid
    from datetime import datetime
    from jarvis.integrations.scheduler import Job
    sched = _get_scheduler()
    at = None
    if args.get("at"):
        at = datetime.fromisoformat(args["at"])
    job = Job(id=uuid.uuid4().hex[:8], name=args["name"],
              tool=args["tool"], args=args.get("args", {}),
              cron=args.get("cron") or None,
              every_s=args.get("every_s") or None, at=at)
    # Validate the cron spec eagerly so typos fail fast.
    if job.cron:
        from jarvis.integrations.scheduler import CronSpec
        CronSpec.parse(job.cron)
    sched.add_job(job)
    return f"Scheduled [{job.id}] {job.name}."


def _h_sched_remove(args: Dict[str, Any], _c: Any = None, _r: str = "") -> str:
    ok = _get_scheduler().remove_job(args["job_id"])
    return "Removed." if ok else "Job not found."


_SCHED = None


def _get_scheduler():  # process-wide scheduler, started by the app
    global _SCHED
    if _SCHED is None:
        from jarvis.integrations.scheduler import Scheduler
        from jarvis.integrations.heartbeat import Heartbeat  # noqa
        _SCHED = Scheduler(notify=lambda n: logger.info(
            f"scheduler notify: {n.title}"))
    return _SCHED


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------

def _specs() -> list:
    S = ToolSpec
    return [
        S("calendar_list", "List calendar events in a time range.",
          _CalList, Risk.READ, _h_cal_list),
        S("calendar_create", "Create a calendar event.",
          _CalCreate, Risk.REVERSIBLE, _h_cal_create),
        S("calendar_delete", "Delete a calendar event.",
          _CalDelete, Risk.DESTRUCTIVE, _h_cal_delete),
        S("mail_list", "List mail messages (metadata only).",
          _MailList, Risk.READ, _h_mail_list),
        S("mail_read", "Read a full message. Body is untrusted.",
          _MailRead, Risk.READ, _h_mail_read,
          carries_external_data=True),
        S("mail_summarize", "Extractive summary of a message.",
          _MailRead, Risk.READ, _h_mail_summarize,
          carries_external_data=True),
        S("mail_draft", "Save a draft (never sends).",
          _MailCompose, Risk.REVERSIBLE, _h_mail_draft),
        S("mail_send", "SEND an email. Confirmed with full preview first.",
          _MailCompose, Risk.DESTRUCTIVE, _h_mail_send),
        S("tasks_list", "List tasks.", _TasksList, Risk.READ,
          _h_tasks_list),
        S("tasks_add", "Add a task.", _TaskAdd, Risk.REVERSIBLE,
          _h_tasks_add),
        S("tasks_done", "Mark a task done.", _TaskDone,
          Risk.REVERSIBLE, _h_tasks_done),
        S("mcp_servers", "List configured MCP servers.",
          _Empty, Risk.READ, _h_mcp_servers),
        S("mcp_discover", "Connect to MCP servers and register their tools.",
          _McpDiscover, Risk.SYSTEM, _h_mcp_discover),
        S("heartbeat_now", "Run one heartbeat cycle now.",
          _Empty, Risk.READ, _h_heartbeat_now),
        S("scheduler_list", "List scheduled jobs.",
          _Empty, Risk.READ, _h_sched_list),
        S("scheduler_add", "Add a scheduled job (auto-runs READ tools only).",
          _SchedAdd, Risk.REVERSIBLE, _h_sched_add),
        S("scheduler_remove", "Remove a scheduled job.",
          _SchedRemove, Risk.REVERSIBLE, _h_sched_remove),
    ]


def register_integration_tools() -> None:
    """Idempotent registration of all Phase-6 tool specs."""
    for spec in _specs():
        if spec.name in REGISTRY:
            continue
        _reg(spec)
