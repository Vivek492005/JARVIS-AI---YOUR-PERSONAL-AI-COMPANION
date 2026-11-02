"""Google Calendar/Gmail/Tasks providers (Master Plan Task 6.3).

Opt-in only: used only when ``JARVIS_PIM_PROVIDER=google`` is set (see
:mod:`jarvis.integrations.pim`). Credentials come from
:mod:`jarvis.core.secrets` — env ``GOOGLE_OAUTH_TOKEN_JSON`` (a JSON
string of the OAuth token) or the OS keyring. Setup is documented in
``docs/INTEGRATIONS_SETUP.md``. **Never hardcode tokens.**

Google API client libraries are lazy-imported so the base install stays
light; a clear error tells the user what to ``pip install``.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from jarvis.integrations.pim import CalEvent, MailMsg, TaskItem

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/tasks",
]


def _service(api: str, version: str) -> Any:
    try:
        from googleapiclient.discovery import build  # type: ignore
        from google.oauth2.credentials import Credentials  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "Google API libraries not installed. Run: "
            "pip install google-api-python-client google-auth-httplib2 "
            "google-auth-oauthlib") from e
    from jarvis.core.secrets import get_secret
    token_json = get_secret("GOOGLE_OAUTH_TOKEN_JSON")
    if not token_json:
        raise RuntimeError(
            "GOOGLE_OAUTH_TOKEN_JSON is not set. See "
            "docs/INTEGRATIONS_SETUP.md for the OAuth setup steps.")
    creds = Credentials.from_authorized_user_info(json.loads(token_json),
                                                  _SCOPES)
    return build(api, version, credentials=creds)


class GoogleCalendar:
    def list_events(self, start: str, end: str) -> List[CalEvent]:
        svc = _service("calendar", "v3")
        items = svc.events().list(
            calendarId="primary", timeMin=start, timeMax=end,
            singleEvents=True, orderBy="startTime",
            maxResults=20).execute().get("items", [])
        out = []
        for it in items:
            out.append(CalEvent(
                id=it.get("id", ""),
                title=it.get("summary", "(no title)"),
                start=(it.get("start") or {}).get("dateTime", ""),
                end=(it.get("end") or {}).get("dateTime", ""),
                location=it.get("location", ""),
                description=it.get("description", "")[:500],
            ))
        return out

    def create_event(self, title: str, start: str, end: str,
                     location: str = "", description: str = "") -> CalEvent:
        svc = _service("calendar", "v3")
        it = svc.events().insert(calendarId="primary", body={
            "summary": title, "location": location,
            "description": description,
            "start": {"dateTime": start}, "end": {"dateTime": end},
        }).execute()
        return CalEvent(id=it.get("id", ""), title=title, start=start,
                        end=end, location=location)

    def delete_event(self, event_id: str) -> bool:
        svc = _service("calendar", "v3")
        svc.events().delete(calendarId="primary",
                            eventId=event_id).execute()
        return True


class GoogleMail:
    def list_messages(self, query: str = "", max_n: int = 10) -> List[MailMsg]:
        svc = _service("gmail", "v1")
        msgs = svc.users().messages().list(
            userId="me", q=query, maxResults=max_n).execute().get(
                "messages", [])
        out = []
        for m in msgs:
            full = svc.users().messages().get(
                userId="me", id=m["id"],
                format="metadata",
                metadataHeaders=["From", "Subject"]).execute()
            headers = {h["name"]: h["value"]
                       for h in full.get("payload", {}).get("headers", [])}
            out.append(MailMsg(
                id=m["id"], sender=headers.get("From", ""),
                subject=headers.get("Subject", ""),
                snippet=full.get("snippet", ""),
                unread="UNREAD" in full.get("labelIds", [])))
        return out

    def read_message(self, msg_id: str) -> Optional[MailMsg]:
        svc = _service("gmail", "v1")
        full = svc.users().messages().get(
            userId="me", id=msg_id, format="full").execute()
        headers = {h["name"]: h["value"]
                   for h in full.get("payload", {}).get("headers", [])}
        body = _extract_body(full.get("payload", {}))
        return MailMsg(id=msg_id, sender=headers.get("From", ""),
                       subject=headers.get("Subject", ""),
                       snippet=full.get("snippet", ""), body=body,
                       unread="UNREAD" in full.get("labelIds", []))

    def draft_message(self, to: str, subject: str, body: str) -> str:
        import base64
        from email.message import EmailMessage
        svc = _service("gmail", "v1")
        msg = EmailMessage()
        msg["To"], msg["Subject"] = to, subject
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        d = svc.users().drafts().create(
            userId="me", body={"message": {"raw": raw}}).execute()
        return d.get("id", "")

    def send_message(self, to: str, subject: str, body: str) -> str:
        import base64
        from email.message import EmailMessage
        svc = _service("gmail", "v1")
        msg = EmailMessage()
        msg["To"], msg["Subject"] = to, subject
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        s = svc.users().messages().send(
            userId="me", body={"raw": raw}).execute()
        return s.get("id", "")


def _extract_body(payload: Dict[str, Any]) -> str:
    """Best-effort plain-text extraction (first text/plain part)."""
    import base64
    mime = payload.get("mimeType", "")
    data = (payload.get("body") or {}).get("data", "")
    if mime.startswith("text/plain") and data:
        try:
            return base64.urlsafe_b64decode(data).decode(
                "utf-8", errors="replace")[:20000]
        except Exception:
            return ""
    for part in payload.get("parts", []) or []:
        text = _extract_body(part)
        if text:
            return text
    return ""


class GoogleTasks:
    def list_tasks(self, include_done: bool = False) -> List[TaskItem]:
        svc = _service("tasks", "v1")
        items = svc.tasks().list(tasklist="@default",
                                 showCompleted=include_done,
                                 maxResults=20).execute().get("items", [])
        return [TaskItem(id=i.get("id", ""), title=i.get("title", ""),
                         done=i.get("status") == "completed",
                         due=i.get("due", ""))
                for i in items]

    def add_task(self, title: str, due: str = "") -> TaskItem:
        svc = _service("tasks", "v1")
        body: Dict[str, str] = {"title": title}
        if due:
            body["due"] = due
        t = svc.tasks().insert(tasklist="@default",
                               body=body).execute()
        return TaskItem(id=t.get("id", ""), title=title, due=due)

    def complete_task(self, task_id: str) -> bool:
        svc = _service("tasks", "v1")
        svc.tasks().patch(tasklist="@default", task=task_id,
                          body={"status": "completed"}).execute()
        return True
