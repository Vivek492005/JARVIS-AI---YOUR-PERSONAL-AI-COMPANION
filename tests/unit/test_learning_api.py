"""Tests for the learning-loop control-center API (Phase 9 moonshot)."""

import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, "src")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jarvis.learning.service import LearningService
from jarvis.server.control import build_control_router


def _gate_pass(ptype, runner=None):
    from jarvis.learning.eval_gate import EvalGateResult

    return EvalGateResult(True, ["safety"], {}, 1.0, "fake pass")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    svc = SimpleNamespace()
    svc.learning = LearningService(db_path=tmp_path / "learning.db", skills_dir=tmp_path / "skills")
    # Seed one pending proposal.
    pid = svc.learning.store.add_proposal(
        "prompt_snippet",
        "get_time:undo",
        "Usage note",
        {"section_title": "Learned: get_time", "markdown": "**get_time**: x"},
        {"corrections": 2},
        0.6,
    )
    svc._seed_pid = pid
    monkeypatch.setattr("jarvis.learning.reviewer.run_eval_gate", _gate_pass)

    def verify():
        return None

    app = FastAPI()
    app.include_router(build_control_router(svc, verify))
    return TestClient(app), svc


def test_status_and_toggle(client):
    c, svc = client
    s = c.get("/api/learning/status").json()
    assert s["enabled"] is True
    assert s["pending_proposals"] == 1
    c.post("/api/learning/disable")
    assert c.get("/api/learning/status").json()["enabled"] is False
    c.post("/api/learning/enable")
    assert c.get("/api/learning/status").json()["enabled"] is True


def test_proposals_list_and_detail(client):
    c, svc = client
    props = c.get("/api/learning/proposals?status=pending").json()
    assert len(props) == 1
    assert props[0]["id"] == svc._seed_pid
    one = c.get(f"/api/learning/proposals/{svc._seed_pid}").json()
    assert one["type"] == "prompt_snippet"
    assert c.get("/api/learning/proposals/LP-9999").status_code == 404


def test_analyze_generates_proposals(client):
    c, svc = client
    for _ in range(3):
        svc.learning.store.add_run(
            tool="get_time", args_redacted={}, args_hash="h1", decision="allow", ok=True
        )
    r = c.post("/api/learning/analyze")
    assert r.status_code == 200
    ids = r.json()["new_proposals"]["reflex_rule"]
    assert len(ids) == 1


def test_approve_applies_with_eval_gate(client, tmp_path):
    c, svc = client
    pid = svc._seed_pid
    # Point the reviewer's prompt path at tmp (service was built with
    # default repo paths; override for the test).
    svc.learning.reviewer.learned_prompt_path = tmp_path / "learned.md"
    r = c.post(f"/api/learning/proposals/{pid}/approve")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["applied_id"] is not None
    assert "Learned: get_time" in (tmp_path / "learned.md").read_text()


def test_reject_and_revert_flow(client):
    c, svc = client
    pid = svc._seed_pid
    r = c.post(f"/api/learning/proposals/{pid}/reject", json={"reason": "not now"})
    assert r.status_code == 200
    # Already decided -> approve is a conflict.
    r = c.post(f"/api/learning/proposals/{pid}/approve")
    assert r.status_code == 409


def test_edit_proposal(client):
    c, svc = client
    pid = svc._seed_pid
    r = c.put(f"/api/learning/proposals/{pid}", json={"title": "edited title"})
    assert r.status_code == 200
    one = c.get(f"/api/learning/proposals/{pid}").json()
    assert one["title"] == "edited title"


def test_ingest_audit(client, monkeypatch):
    c, svc = client
    monkeypatch.setattr(
        "jarvis.policy.audit.query",
        lambda **kw: [
            {"tool": "get_time", "args": {}, "decision": "allow", "latency_ms": 2.0, "reason": "ok"}
        ],
    )
    r = c.post("/api/learning/ingest-audit?limit=10")
    assert r.status_code == 200
    assert r.json()["ingested"] == 1
    assert svc.learning.store.count_runs() == 1


def test_runs_endpoint(client):
    c, svc = client
    svc.learning.store.add_run(tool="get_time", args_redacted={}, args_hash="h", decision="allow")
    rows = c.get("/api/learning/runs?limit=5").json()
    assert len(rows) == 1
    assert rows[0]["tool"] == "get_time"
