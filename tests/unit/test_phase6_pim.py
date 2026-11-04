"""Tests for Task 6.3 (Calendar / Mail / Tasks)."""

import pytest

from jarvis.integrations import pim
from jarvis.integrations.pim import FakeCalendar, FakeMail, FakeTasks
from jarvis.tools.registry import Risk, resolve


@pytest.fixture(autouse=True)
def _reset():
    pim.reset_providers()
    yield
    pim.reset_providers()


def test_fake_calendar_crud():
    cal = FakeCalendar()
    e = cal.create_event("Standup", "2026-11-03T09:00", "2026-11-03T09:15")
    assert e.id
    found = cal.list_events("2026-11-03T00:00", "2026-11-03T23:59")
    assert [x.id for x in found] == [e.id]
    assert cal.delete_event(e.id) is True
    assert cal.delete_event(e.id) is False


def test_fake_mail_flow():
    mail = FakeMail()
    m = mail.seed("boss@corp.com", "Q4 planning", "Please review the plan.")
    assert mail.list_messages("planning")[0].id == m.id
    assert mail.read_message(m.id).body == "Please review the plan."
    assert mail.draft_message("a@b.c", "s", "b").startswith("draft-")
    assert mail.send_message("a@b.c", "s", "b").startswith("sent-")
    assert mail.list_messages("zzz") == []


def test_fake_tasks_flow():
    t = FakeTasks()
    item = t.add_task("Buy milk", due="2026-11-04")
    assert [x.id for x in t.list_tasks()] == [item.id]
    assert t.complete_task(item.id) is True
    assert t.list_tasks() == []
    assert t.list_tasks(include_done=True)[0].done is True


def test_tool_risk_tiers():
    assert resolve("calendar_list", {}).risk == Risk.READ
    assert (
        resolve("calendar_create", {"title": "x", "start": "s", "end": "e"}).risk == Risk.REVERSIBLE
    )
    assert resolve("calendar_delete", {"event_id": "1"}).risk == Risk.DESTRUCTIVE
    assert resolve("mail_list", {}).risk == Risk.READ
    assert resolve("mail_read", {"msg_id": "1"}).risk == Risk.READ
    assert resolve("mail_draft", {"to": "a", "subject": "s", "body": "b"}).risk == Risk.REVERSIBLE
    assert resolve("mail_send", {"to": "a", "subject": "s", "body": "b"}).risk == Risk.DESTRUCTIVE
    assert resolve("tasks_add", {"title": "x"}).risk == Risk.REVERSIBLE


def test_mail_body_marked_untrusted():
    spec = resolve("mail_read", {"msg_id": "1"})
    assert spec.carries_external_data is True
    spec2 = resolve("mail_summarize", {"msg_id": "1"})
    assert spec2.carries_external_data is True


def test_mail_send_needs_confirmation_by_default():
    # DESTRUCTIVE at default autonomy -> CONFIRM via run_action.
    from jarvis.tools.actions import run_action

    verdict, result = run_action("mail_send", {"to": "a@b.c", "subject": "hi", "body": "hello"})
    assert verdict == "confirm"
    assert "a@b.c" in result  # full preview in the prompt


def test_mail_send_handler_only_after_allow(monkeypatch):
    # The handler itself just sends; the gate is what protects.
    from jarvis.integrations import tools as tmod

    mail = FakeMail()
    monkeypatch.setattr(pim, "get_mail", lambda: mail)
    out = tmod._h_mail_send({"to": "a@b.c", "subject": "s", "body": "b"})
    assert "Sent to a@b.c" in out


def test_mail_read_wraps_untrusted(monkeypatch):
    from jarvis.integrations import tools as tmod

    mail = FakeMail()
    mail.seed("x@y.z", "sub", "secret body here")
    monkeypatch.setattr(tmod, "get_mail", lambda: mail)
    out = tmod._h_mail_read({"msg_id": "m1"})
    assert "<untrusted_data>" in out and "secret body here" in out


def test_default_provider_is_fake():
    assert isinstance(pim.get_calendar(), FakeCalendar)
    assert isinstance(pim.get_mail(), FakeMail)
    assert isinstance(pim.get_tasks(), FakeTasks)


def test_google_provider_opt_in_only(monkeypatch):
    import jarvis.core.secrets as sec

    monkeypatch.setattr(
        sec, "get_secret", lambda name: "google" if name == "JARVIS_PIM_PROVIDER" else ""
    )
    # Opt-in selects the Google provider; the helpful error surfaces on use.
    assert isinstance(pim.get_calendar(), pim._google_calendar().__class__)
    with pytest.raises(RuntimeError, match="not installed|GOOGLE_OAUTH"):
        pim.get_calendar().list_events("2026-01-01", "2026-01-02")


def test_google_provider_import_error_message(monkeypatch):
    from jarvis.integrations import google_pim
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name.startswith("googleapiclient") or name.startswith("google.oauth2"):
            raise ImportError("nope")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match="pip install"):
        google_pim._service("calendar", "v3")
