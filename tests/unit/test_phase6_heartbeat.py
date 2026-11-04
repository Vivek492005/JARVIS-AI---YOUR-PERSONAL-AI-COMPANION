"""Tests for Task 6.4 (heartbeat)."""

from datetime import datetime

from jarvis.integrations.heartbeat import (
    Heartbeat,
    HeartbeatConfig,
    in_quiet_hours,
)


def dt(h=12, mi=0):
    return datetime(2026, 11, 2, h, mi)


def _hb(notes, **kw):
    cfg = HeartbeatConfig(**kw)
    return Heartbeat(config=cfg, notify=notes.append, now_fn=lambda: dt())


def test_quiet_hours_overnight():
    assert in_quiet_hours(dt(h=23, mi=30)) is True
    assert in_quiet_hours(dt(h=2)) is True
    assert in_quiet_hours(dt(h=6, mi=59)) is True
    assert in_quiet_hours(dt(h=7)) is False
    assert in_quiet_hours(dt(h=12)) is False
    assert in_quiet_hours(dt(h=22, mi=59)) is False


def test_heartbeat_ok_when_nothing(monkeypatch):
    from jarvis.integrations import heartbeat as hbmod

    monkeypatch.setattr(hbmod.Heartbeat, "_run_read", lambda s, t, a: "")
    notes = []
    hb = _hb(notes)
    assert hb.tick() == "HEARTBEAT_OK"
    assert notes == []


def test_heartbeat_calendar_meeting(monkeypatch):
    from jarvis.integrations import heartbeat as hbmod

    def fake_read(self, tool, args):
        if tool == "calendar_list":
            return "[ev1] Standup | 2026-11-02T12:10 -> 12:20"
        return ""

    monkeypatch.setattr(hbmod.Heartbeat, "_run_read", fake_read)
    notes = []
    hb = _hb(notes)
    assert hb.tick() == "NOTIFIED"
    assert len(notes) == 1 and "Standup" in notes[0].body


def test_quiet_hours_holds_normal_but_not_urgent(monkeypatch):
    from jarvis.integrations import heartbeat as hbmod

    def fake_read(self, tool, args):
        if tool == "calendar_list":
            return "[ev1] Standup | x"
        if tool == "system_control":
            return "Battery: 5% (discharging)"  # urgent
        return ""

    monkeypatch.setattr(hbmod.Heartbeat, "_run_read", fake_read)
    notes = []
    hb = Heartbeat(
        config=HeartbeatConfig(), notify=notes.append, now_fn=lambda: dt(h=2)
    )  # 02:00, quiet
    hb.tick()
    kinds = [n.title for n in notes]
    assert "Battery low" in kinds  # urgent passes
    assert "Meeting in 30 minutes" not in kinds  # normal held


def test_rate_limit_caps_proactive(monkeypatch):
    from jarvis.integrations import heartbeat as hbmod

    monkeypatch.setattr(
        hbmod.Heartbeat, "_run_read", lambda s, t, a: "[ev1] x" if t == "calendar_list" else ""
    )
    notes = []
    hb = _hb(notes, max_per_day=2)
    assert hb.tick() == "NOTIFIED"
    assert hb.tick() == "NOTIFIED"
    assert hb.tick() == "HEARTBEAT_OK"  # budget exhausted
    assert len(notes) == 2


def test_non_read_check_tools_skipped(monkeypatch):
    # A heartbeat check whose tool is above READ must be skipped, never run.
    from jarvis.tools import actions as actmod

    calls = []
    monkeypatch.setattr(actmod, "run_action", lambda t, a: calls.append(t) or ("allow", "x"))
    hb = _hb([])
    assert hb._run_read("mail_send", {"to": "a", "subject": "s", "body": "b"}) is None
    assert calls == []


def test_daily_brief_opt_in_once(monkeypatch):
    from jarvis.integrations import heartbeat as hbmod

    monkeypatch.setattr(hbmod.Heartbeat, "_run_read", lambda s, t, a: "some data")
    notes = []
    hb = Heartbeat(
        config=HeartbeatConfig(
            rules={
                "calendar_meeting": False,
                "mail_vip": False,
                "battery_low": False,
                "daily_brief": True,
            }
        ),
        notify=notes.append,
        now_fn=lambda: dt(h=8),
    )
    assert hb.tick() == "NOTIFIED"
    assert any(n.title == "Daily Brief" for n in notes)
    notes.clear()
    assert hb.tick() == "HEARTBEAT_OK"  # once per day


def test_daily_brief_opt_out_by_default(monkeypatch):
    from jarvis.integrations import heartbeat as hbmod

    monkeypatch.setattr(hbmod.Heartbeat, "_run_read", lambda s, t, a: "some data")
    notes = []
    hb = _hb(notes)  # daily_brief False
    hb.tick()
    assert all(n.title != "Daily Brief" for n in notes)
