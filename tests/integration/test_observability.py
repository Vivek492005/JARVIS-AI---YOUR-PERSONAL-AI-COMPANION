"""Tests for Task 2.7: observability + jarvis doctor."""

import json
import logging
import random
from unittest import mock

import pytest

from jarvis.brain.router import Router
from jarvis.brain.reflex import ReflexMatcher, ReflexStats
from jarvis.core.doctor import Check, all_checks, run_doctor
from jarvis.core.logging import (
    JsonFormatter,
    StageTimer,
    get_trace_id,
    new_trace_id,
    set_trace_id,
    setup_logging,
)
from jarvis.core.metrics import MetricsRecorder


@pytest.fixture()
def tmp_metrics(tmp_path):
    return MetricsRecorder(metrics_dir=str(tmp_path / "metrics"))


@pytest.fixture()
def router(tmp_path, tmp_metrics):
    stats = ReflexStats(path=str(tmp_path / "stats.json"))
    return Router(
        reflex=ReflexMatcher(stats=stats, rng=random.Random(0)),
        agent=mock.MagicMock(),
        metrics=tmp_metrics,
    )


# -- logging ---------------------------------------------------------------


def test_trace_id_roundtrip():
    t = new_trace_id()
    assert len(t) == 16
    set_trace_id(t)
    assert get_trace_id() == t
    set_trace_id("")


def test_json_formatter_includes_trace():
    fmt = JsonFormatter()
    rec = logging.LogRecord("jarvis.test", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    set_trace_id("trace123")
    try:
        payload = json.loads(fmt.format(rec))
    finally:
        set_trace_id("")
    assert payload["msg"] == "hello world"
    assert payload["trace"] == "trace123"
    assert payload["level"] == "INFO"


def test_setup_logging_idempotent():
    setup_logging(json_output=True)
    setup_logging(json_output=True)  # second call is a no-op
    root = logging.getLogger("jarvis")
    assert len(root.handlers) == 1


def test_stage_timer_records_ms():
    import time

    with StageTimer() as st:
        with st.stage("work"):
            time.sleep(0.01)
    assert st.timings["work"] >= 5.0
    assert st.timings["total"] >= st.timings["work"]


# -- metrics ----------------------------------------------------------------


def test_metrics_record_writes_csv(tmp_metrics, tmp_path):
    tmp_metrics.record(
        "t1", "reflex", {"reflex_match": 1.2, "run": 3.4, "total": 5.0}, provider="reflex"
    )
    tmp_metrics.record("t2", "llm", {"total": 100.0}, provider="deepseek", degraded=True)
    rows = tmp_metrics.tail(10)
    assert len(rows) == 2
    assert rows[0]["trace"] == "t1" and rows[0]["path"] == "reflex"
    assert rows[0]["provider"] == "reflex" and rows[0]["degraded"] == "0"
    assert rows[1]["degraded"] == "1"
    # header present on disk
    day_file = list((tmp_path / "metrics").glob("*.csv"))[0]
    with open(day_file) as f:
        assert f.readline().strip().startswith("ts,trace,path")


def test_metrics_never_raises(tmp_path):
    rec = MetricsRecorder(metrics_dir=str(tmp_path / "nope" / "deep"))
    # unwritable dir is handled inside; record must not raise either way
    rec.record("t", "llm", {})


# -- router integration ------------------------------------------------------


def test_router_handle_traces_and_records_metrics(router, tmp_metrics):
    with mock.patch("jarvis.tools.actions.run_action", return_value=("allow", "tool-output")):
        out = router.handle("open youtube")
    assert out == "Opening YouTube"
    rows = tmp_metrics.tail(5)
    assert len(rows) == 1
    row = rows[0]
    assert row["path"] == "reflex" and row["provider"] == "reflex"
    assert len(row["trace"]) == 16
    assert float(row["total_ms"]) >= 0.0


def test_router_llm_path_records_provider(tmp_path, tmp_metrics):
    agent = mock.MagicMock()
    agent.process.return_value = "llm!"
    fake_res = mock.MagicMock(provider_name="deepseek", degraded=True)
    type(agent).last_chain_result = mock.PropertyMock(return_value=fake_res)
    stats = ReflexStats(path=str(tmp_path / "stats.json"))
    r = Router(reflex=ReflexMatcher(stats=stats), agent=agent, metrics=tmp_metrics)
    assert r.handle("xqzw blorpt fnord") == "llm!"
    row = tmp_metrics.tail(5)[0]
    assert row["path"] == "llm"
    assert row["provider"] == "deepseek" and row["degraded"] == "1"


def test_router_metrics_failure_does_not_break_turn(tmp_path):
    stats = ReflexStats(path=str(tmp_path / "stats.json"))
    bad_metrics = mock.MagicMock()
    bad_metrics.record.side_effect = RuntimeError("disk on fire")
    r = Router(
        reflex=ReflexMatcher(stats=stats, rng=random.Random(0)),
        agent=mock.MagicMock(),
        metrics=bad_metrics,
    )
    assert r.handle("flip a coin") in ("It's Heads!", "It's Tails!")


# -- doctor ------------------------------------------------------------------


def test_all_checks_shape():
    checks = all_checks()
    assert len(checks) >= 10
    for c in checks:
        assert isinstance(c, Check)
        assert c.status in ("ok", "warn", "fail")
        assert c.name


def test_run_doctor_exit_codes(capsys):
    from jarvis.core import doctor as d

    ok_checks = [Check("a", "ok", "fine"), Check("b", "warn", "meh")]
    with mock.patch.object(d, "all_checks", return_value=ok_checks):
        assert run_doctor(verbose=False) == 0
    bad_checks = [Check("a", "fail", "broken")]
    with mock.patch.object(d, "all_checks", return_value=bad_checks):
        assert run_doctor(verbose=True) == 1
    out = capsys.readouterr().out
    assert "broken" in out


def test_doctor_degrades_gracefully_without_mic():
    from jarvis.core import doctor as d

    with mock.patch.dict("sys.modules", {"speech_recognition": None}):
        # sys.modules[...] = None makes `import` raise ImportError
        c = d.check_mic()
    assert c.status == "warn"


def test_doctor_packages_source_checkout_warns_not_fails():
    from jarvis.core import doctor as d
    import importlib.metadata as md

    real_version = md.version

    def fake_version(dist):
        if dist == "jarvis-assistant":
            raise md.PackageNotFoundError()
        return real_version(dist)

    with mock.patch.object(md, "version", side_effect=fake_version):
        c = d.check_packages()
    assert c.status in ("ok", "warn")  # never fail for source checkouts
