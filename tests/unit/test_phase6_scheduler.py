"""Tests for Task 6.4 (scheduler + heartbeat)."""

from datetime import datetime, timedelta

import pytest

from jarvis.integrations.scheduler import (
    CronSpec, Job, Scheduler, _cron_matches,
)


def dt(y=2026, mo=11, d=2, h=12, mi=0):
    return datetime(y, mo, d, h, mi)


def test_cron_every_30_min():
    spec = CronSpec.parse("*/30 * * * *")
    assert _cron_matches(spec, dt(mi=0))
    assert _cron_matches(spec, dt(mi=30))
    assert not _cron_matches(spec, dt(mi=15))


def test_cron_lists_ranges_steps():
    assert _cron_matches(CronSpec.parse("0 9 * * 1-5"), dt(h=9, d=3))  # Tue
    assert not _cron_matches(CronSpec.parse("0 9 * * 1-5"), dt(h=9, d=1))  # Sun
    assert _cron_matches(CronSpec.parse("0 0 1 * *"), dt(d=1, h=0))
    assert not _cron_matches(CronSpec.parse("0 0 1 * *"), dt(d=2, h=0))


def test_cron_bad_spec():
    with pytest.raises(ValueError):
        CronSpec.parse("* * *")


def test_job_due_cron_fires_once_per_minute():
    job = Job(id="j", name="n", tool="t", cron="* * * * *")
    now = dt(mi=5)
    assert job.due(now) is True
    job.last_run = now
    assert job.due(now) is False                      # same minute: no refire
    assert job.due(now + timedelta(minutes=1)) is True


def test_job_due_every_and_at():
    job = Job(id="j", name="n", tool="t", every_s=60)
    assert job.due(dt()) is True
    job.last_run = dt()
    assert job.due(dt()) is False
    assert job.due(dt() + timedelta(seconds=61)) is True

    job2 = Job(id="k", name="n", tool="t", at=dt(h=13))
    assert job2.due(dt(h=12)) is False
    assert job2.due(dt(h=13)) is True
    job2.last_run = dt(h=13)
    assert job2.due(dt(h=14)) is False                 # one-shot


def test_scheduler_runs_read_tool_silently(monkeypatch):
    from jarvis.tools import actions as actmod
    calls = []

    def fake_run(tool, args):
        calls.append((tool, args))
        return ("allow", "ok")

    monkeypatch.setattr(actmod, "run_action", fake_run)
    notes = []
    sched = Scheduler(notify=notes.append)
    sched.add_job(Job(id="j", name="n", tool="calendar_list",
                      every_s=10))
    sched.tick(dt())
    assert calls == [("calendar_list", {})]
    assert notes == []


def test_scheduler_never_silently_runs_above_read(monkeypatch):
    from jarvis.tools import actions as actmod
    calls = []
    monkeypatch.setattr(actmod, "run_action",
                        lambda t, a: calls.append(t) or ("allow", "x"))
    notes = []
    sched = Scheduler(notify=notes.append)
    # mail_send is DESTRUCTIVE
    sched.add_job(Job(id="j", name="evil", tool="mail_send",
                      args={"to": "a", "subject": "s", "body": "b"},
                      every_s=10))
    sched.tick(dt())
    assert calls == []                                 # NOT executed
    assert len(notes) == 1 and "Confirm" in notes[0].body


def test_scheduler_unknown_tool_notifies():
    notes = []
    sched = Scheduler(notify=notes.append)
    sched.add_job(Job(id="j", name="n", tool="nope_nope", every_s=10))
    sched.tick(dt())
    assert len(notes) == 1 and "Unknown tool" in notes[0].body


def test_scheduler_blocked_verdict_notifies(monkeypatch):
    from jarvis.tools import actions as actmod
    monkeypatch.setattr(actmod, "run_action",
                        lambda t, a: ("deny", "Blocked for safety: x"))
    notes = []
    sched = Scheduler(notify=notes.append)
    sched.add_job(Job(id="j", name="n", tool="calendar_list", every_s=10))
    sched.tick(dt())
    assert len(notes) == 1


def test_file_watch_triggers_on_change(tmp_path):
    notes = []
    sched = Scheduler(notify=notes.append)
    p = tmp_path / "watched.txt"
    p.write_text("v1")
    fired = []
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(Scheduler, "_fire",
                        lambda self, job, now: fired.append(job.id))
    try:
        sched.add_job(Job(id="w", name="watch", tool="calendar_list",
                          watch_file=str(p)))
        sched.tick(dt())
        assert fired == []                             # baseline hash only
        p.write_text("v2")
        sched.tick(dt())
        assert fired == ["w"]
    finally:
        monkeypatch.undo()


def test_scheduler_add_remove():
    sched = Scheduler(notify=lambda n: None)
    sched.add_job(Job(id="a", name="n", tool="t"))
    assert len(sched.list_jobs()) == 1
    assert sched.remove_job("a") is True
    assert sched.remove_job("a") is False
