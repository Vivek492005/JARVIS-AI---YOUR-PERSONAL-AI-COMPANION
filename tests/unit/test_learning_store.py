"""Tests for the learning store (Phase 9 moonshot)."""

import json
import sys

import pytest

sys.path.insert(0, "src")

from jarvis.learning.store import LearningStore


@pytest.fixture()
def store(tmp_path):
    s = LearningStore(tmp_path / "learning.db")
    yield s
    s.close()


def test_enabled_flag_defaults_on(store):
    assert store.is_enabled() is True
    store.set_enabled(False)
    assert store.is_enabled() is False
    store.set_enabled(True)
    assert store.is_enabled() is True


def test_add_and_recent_runs(store):
    rid = store.add_run(
        tool="get_time",
        args_redacted={},
        args_hash="abc123",
        decision="allow",
        ok=True,
        latency_ms=12.5,
        path="llm",
        source_trust="local",
    )
    assert rid == 1
    rows = store.recent_runs()
    assert len(rows) == 1
    assert rows[0]["tool"] == "get_time"
    assert rows[0]["learnable"] == 1
    assert rows[0]["ok"] == 1


def test_unlearnable_rows_excluded_by_default(store):
    store.add_run(
        tool="mcp.fs.read",
        args_redacted={},
        args_hash="x",
        decision="allow",
        source_trust="mcp",
        learnable=False,
    )
    assert store.recent_runs() == []
    assert len(store.recent_runs(learnable_only=False)) == 1


def test_run_clusters(store):
    for _ in range(4):
        store.add_run(tool="get_time", args_redacted={}, args_hash="h1", decision="allow", ok=True)
    store.add_run(tool="get_time", args_redacted={}, args_hash="h2", decision="allow", ok=True)
    clusters = store.run_clusters(min_count=3)
    assert len(clusters) == 1
    assert clusters[0]["tool"] == "get_time"
    assert clusters[0]["n"] == 4
    assert clusters[0]["n_allow"] == 4


def test_corrections_and_clusters(store):
    store.add_correction("undo", "set_volume", note="too loud")
    store.add_correction("undo", "set_volume")
    store.add_correction("undo", "other_tool")
    clusters = store.correction_clusters(min_count=2)
    assert len(clusters) == 1
    assert clusters[0]["tool"] == "set_volume"
    assert clusters[0]["n"] == 2


def test_proposal_lifecycle(store):
    pid = store.add_proposal("reflex_rule", "get_time:h1", "title", {"rule": {}}, {"n": 3}, 0.6)
    assert pid == "LP-0001"
    assert store.proposal_exists_for("reflex_rule", "get_time:h1") is True
    assert store.proposal_exists_for("reflex_rule", "other") is False
    p = store.get_proposal(pid)
    assert p["status"] == "pending"
    assert json.loads(p["body"]) == {"rule": {}}
    assert store.update_proposal(pid, status="rejected", decision_reason="nope") is True
    assert store.get_proposal(pid)["status"] == "rejected"
    assert store.update_proposal(pid, bogus_field="x") is False
    assert store.list_proposals("pending") == []
    assert len(store.list_proposals()) == 1


def test_applied_and_revert_tracking(store):
    aid = store.record_applied("LP-0001", "reflex_rule", "/tmp/x.json", {"previous": []})
    rec = store.get_applied(aid)
    assert rec["reversible"] == 1
    assert rec["reverted_ts"] is None
    assert store.mark_reverted(aid) is True
    assert store.mark_reverted(aid) is False  # already reverted
    assert store.get_applied(aid)["reverted_ts"] is not None
    assert store.list_applied(include_reverted=False) == []


def test_counts(store):
    store.add_run(tool="a", args_redacted={}, args_hash="1", decision="allow")
    store.add_run(tool="b", args_redacted={}, args_hash="2", decision="allow", learnable=False)
    store.add_correction("undo", "a")
    assert store.count_runs() == 2
    assert store.count_runs(learnable_only=True) == 1
    assert store.count_corrections() == 1
