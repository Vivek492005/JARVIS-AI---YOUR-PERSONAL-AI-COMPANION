"""Tests for the learning recorder (Phase 9 moonshot).

Privacy + poisoning guards:
* args are stored redacted (audit redaction);
* sensitive content is withheld entirely (hash only);
* untrusted sources (mcp.* tools, web/clipboard) are never learnable;
* nothing is recorded when the loop is disabled;
* recorder never raises.
"""

import sys

import pytest

sys.path.insert(0, "src")

from jarvis.learning.recorder import LearningRecorder, record_undo_event
from jarvis.learning.store import LearningStore


@pytest.fixture()
def store(tmp_path):
    s = LearningStore(tmp_path / "learning.db")
    yield s
    s.close()


@pytest.fixture()
def rec(store):
    return LearningRecorder(store)


def test_record_run_basic(rec, store):
    rid = rec.record_run("get_time", {}, decision="allow", ok=True,
                         latency_ms=5.0, path="llm")
    assert rid is not None
    rows = store.recent_runs(learnable_only=False)
    assert rows[0]["tool"] == "get_time"
    assert rows[0]["path"] == "llm"
    assert rows[0]["source_trust"] == "local"


def test_args_are_redacted(rec, store):
    # ghp_...-looking values must not survive even in redacted form.
    rec.record_run("some_tool", {"api_key": "ghp_abcdefgh12345678"},
                   decision="allow")
    import json
    rows = store.recent_runs(learnable_only=False)
    stored = json.loads(rows[0]["args_redacted"])
    assert stored["api_key"] == "***REDACTED***"


def test_sensitive_content_withheld(rec, store):
    rec.record_run("note_tool", {"text": "my password: hunter2-hunter2"},
                   decision="allow")
    rows = store.recent_runs(learnable_only=False)
    assert rows[0]["withheld"] == 1
    import json
    assert json.loads(rows[0]["args_redacted"]) == {}
    # ...but the hash survives for counting/dedup.
    assert rows[0]["args_hash"]


def test_mcp_tool_never_learnable(rec, store):
    rec.record_run("mcp.filesystem.read", {"path": "/etc/passwd"},
                   decision="allow", source_trust="local")
    rows = store.recent_runs(learnable_only=False)
    assert rows[0]["source_trust"] == "mcp"
    assert rows[0]["learnable"] == 0
    assert store.recent_runs() == []


def test_untrusted_source_never_learnable(rec, store):
    rec.record_run("web_search", {"q": "x"}, decision="allow",
                   source_trust="web")
    rows = store.recent_runs(learnable_only=False)
    assert rows[0]["learnable"] == 0


def test_disabled_is_noop(rec, store):
    store.set_enabled(False)
    assert rec.record_run("get_time", {}, decision="allow") is None
    assert rec.record_correction("undo", "get_time") is None
    assert rec.ingest_audit([{"tool": "get_time", "decision": "allow",
                              "args": {}}]) == 0
    assert store.count_runs() == 0


def test_record_correction_kinds(rec, store):
    assert rec.record_correction("undo", "set_volume") is not None
    assert rec.record_correction("bogus", "set_volume") is None
    assert store.count_corrections() == 1


def test_ingest_audit(rec, store):
    entries = [
        {"tool": "get_time", "args": {"x": 1}, "decision": "allow",
         "latency_ms": 3.0, "reason": "ok"},
        {"tool": "mcp.evil", "args": {}, "decision": "allow"},
        {"tool": "learning.approve", "args": {},
         "decision": "allow"},  # control-plane: skipped
        {"tool": "", "decision": "allow"},  # skipped
        {"tool": "open_app", "args": {}, "decision": "deny"},
    ]
    assert rec.ingest_audit(entries) == 3
    rows = {r["tool"]: r for r in
            store.recent_runs(learnable_only=False)}
    assert rows["get_time"]["ok"] == 1
    assert rows["mcp.evil"]["learnable"] == 0
    assert rows["open_app"]["ok"] == 0


def test_record_undo_event_never_raises(tmp_path, monkeypatch):
    # Points the module-level hook at a throwaway DB, then breaks the
    # store to prove the hook still cannot raise.
    import jarvis.learning.recorder as recmod
    monkeypatch.setattr(recmod, "_recorder", None)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    record_undo_event("set_volume", {"level": 11}, "set_volume (undo)")
    assert recmod._recorder is not None
    assert recmod._recorder.store.count_corrections() == 1
