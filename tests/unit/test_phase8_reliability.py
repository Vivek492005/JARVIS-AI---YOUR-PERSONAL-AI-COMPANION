"""Tests for Task 8.3 (reliability): watchdog, crash reports, migrations,
safe mode, offline mode."""

import json
import os

import pytest

from jarvis.core import migrations
from jarvis.core.crash import write_crash_report
from jarvis.core.watchdog import Watchdog, WatchdogConfig
from jarvis.policy import Decision, PolicyContext, Risk, context_from_settings, decide
from jarvis.tools.registry import ToolSpec
from pydantic import BaseModel


class _P(BaseModel):
    pass


def _spec(risk):
    return ToolSpec(name="t", description="t", params=_P, risk=risk, handler=lambda a, b, c: "")


# --- watchdog ---------------------------------------------------------------


def test_watchdog_backoff_caps():
    w = Watchdog(WatchdogConfig(command=["x"], backoff_base_s=2.0, backoff_max_s=60.0))
    assert w._backoff(0) == 2.0
    assert w._backoff(1) == 4.0
    assert w._backoff(10) == 60.0  # capped


def test_watchdog_clean_exit_returns_zero(monkeypatch):
    w = Watchdog(WatchdogConfig(command=["x"]))
    monkeypatch.setattr(w, "run_once", lambda: 0)
    assert w.supervise() == 0


def test_watchdog_gives_up_after_max_restarts(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    w = Watchdog(WatchdogConfig(command=["x"], max_restarts=2, backoff_base_s=0, window_s=3600))
    calls = []
    monkeypatch.setattr(w, "run_once", lambda: calls.append(1) or 1)  # always crash
    assert w.supervise() == 1
    assert len(calls) == 3  # initial + 2 restarts, then give up
    # one crash report per crash
    reports = list((tmp_path / ".jarvis" / "crashes").glob("crash-*.json"))
    assert len(reports) == 3


def test_watchdog_stop(monkeypatch):
    w = Watchdog(WatchdogConfig(command=["x"], backoff_base_s=0))
    monkeypatch.setattr(w, "run_once", lambda: w.stop() or 1)
    assert w.supervise() == 0


# --- crash reports ----------------------------------------------------------


def test_crash_report_written_locally(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    path = write_crash_report("boom", context={"a": 1})
    assert path and os.path.exists(path)
    data = json.load(open(path))
    assert data["summary"] == "boom"
    assert data["context"] == {"a": 1}


def test_crash_report_with_exception(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    try:
        raise ValueError("nope")
    except ValueError as e:
        path = write_crash_report("with exc", exc=e)
    data = json.load(open(path))
    assert "ValueError: nope" in data["traceback"]


def test_crash_report_never_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "nonexistent-parent"))
    # HOME points nowhere writable-ish; must still not raise
    assert isinstance(write_crash_report("x"), str)


# --- migrations -------------------------------------------------------------


def test_migrate_0_to_1_adds_new_keys():
    out = migrations.migrate_settings({})
    assert out["schema_version"] == 1
    assert out["safety"]["safe_mode"] is False
    assert out["privacy"]["offline"] is False
    assert out["privacy"]["crash_upload"] is False


def test_migrate_preserves_user_keys():
    out = migrations.migrate_settings({"safety": {"autonomy_level": 2}, "custom": {"x": 1}})
    assert out["safety"]["autonomy_level"] == 2
    assert out["custom"] == {"x": 1}
    assert out["schema_version"] == 1


def test_migrate_idempotent():
    once = migrations.migrate_settings({})
    assert migrations.migrate_settings(once) == once
    assert not migrations.needs_migration(once)
    assert migrations.needs_migration({})


# --- safe mode / offline policy ---------------------------------------------


@pytest.mark.parametrize("risk", [Risk.REVERSIBLE, Risk.DESTRUCTIVE, Risk.SYSTEM])
def test_safe_mode_denies_above_read(risk):
    ctx = PolicyContext(safe_mode=True)
    assert decide(_spec(risk), ctx, 3) is Decision.DENY


def test_safe_mode_allows_read():
    ctx = PolicyContext(safe_mode=True)
    assert decide(_spec(Risk.READ), ctx, 3) is Decision.ALLOW


def test_offline_denies_network_tools():
    spec = _spec(Risk.READ)
    object.__setattr__(spec, "scopes", frozenset({"network"}))
    assert decide(spec, PolicyContext(offline=True), 3) is Decision.DENY


def test_offline_allows_local_tools():
    assert decide(_spec(Risk.READ), PolicyContext(offline=True), 3) is Decision.ALLOW


def test_context_from_settings_safe_mode(monkeypatch, tmp_path):
    from jarvis.core.config import reset_settings_cache

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("safety__safe_mode", "true")
    monkeypatch.setenv("privacy__offline", "true")
    reset_settings_cache()
    try:
        ctx = context_from_settings()
        assert ctx.safe_mode is True
        assert ctx.offline is True
    finally:
        reset_settings_cache()


def test_cloud_egress_allowed():
    from jarvis.core.config import Settings, cloud_egress_allowed

    assert cloud_egress_allowed(Settings()) is True
    assert cloud_egress_allowed(Settings(privacy={"offline": True})) is False
    assert cloud_egress_allowed(Settings(privacy={"privacy_mode": True})) is False


def test_pim_offline_forces_fake(monkeypatch, tmp_path):
    from jarvis.core.config import reset_settings_cache
    from jarvis.integrations import pim

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("privacy__offline", "true")
    monkeypatch.setenv("JARVIS_PIM_PROVIDER", "google")
    reset_settings_cache()
    pim.reset_providers()
    try:
        assert pim._provider_kind() == "fake"
        assert type(pim.get_calendar()).__name__ == "FakeCalendar"
    finally:
        reset_settings_cache()
        pim.reset_providers()


def test_cli_safe_flag_parses():
    from jarvis.cli import build_parser

    args = build_parser().parse_args(["--safe", "doctor"])
    assert args.safe is True
    args2 = build_parser().parse_args(["doctor"])
    assert args2.safe is False
