"""Tests for the proposal generator (Phase 9 moonshot)."""

import json
import sys

import pytest

sys.path.insert(0, "src")

from jarvis.learning import proposer
from jarvis.learning.store import LearningStore


@pytest.fixture()
def store(tmp_path):
    s = LearningStore(tmp_path / "learning.db")
    yield s
    s.close()


def _run(store, tool, h, n=3, **kw):
    for _ in range(n):
        store.add_run(
            tool=tool, args_redacted={"a": 1}, args_hash=h, decision="allow", ok=True, **kw
        )


def test_reflex_rule_proposal(store):
    _run(store, "get_time", "h1", n=4)
    _run(store, "get_time", "h2", n=2)  # below threshold
    ids = proposer.propose_reflex_rules(store, min_evidence=3)
    assert len(ids) == 1
    p = store.get_proposal(ids[0])
    assert p["type"] == "reflex_rule"
    assert p["status"] == "pending"
    body = json.loads(p["body"])
    rule = body["rule"]
    assert rule["tool"] == "get_time"
    assert rule["id"].startswith("learned_get_time_")
    # Privacy: patterns are EMPTY — the reviewer fills them in.
    assert rule["patterns"] == []
    ev = json.loads(p["evidence"])
    assert ev["runs"] == 4


def test_reflex_proposal_dedup(store):
    _run(store, "get_time", "h1", n=3)
    assert len(proposer.propose_reflex_rules(store, min_evidence=3)) == 1
    # Second run: no duplicate pending proposal.
    assert proposer.propose_reflex_rules(store, min_evidence=3) == []


def test_unlearnable_runs_never_propose(store):
    _run(store, "mcp.fs.read", "h9", n=5, source_trust="mcp", learnable=False)
    assert proposer.propose_reflex_rules(store, min_evidence=3) == []


def test_prompt_snippet_proposal(store):
    store.add_correction("undo", "set_volume")
    store.add_correction("undo", "set_volume")
    ids = proposer.propose_prompt_snippets(store, min_evidence=2)
    assert len(ids) == 1
    p = store.get_proposal(ids[0])
    body = json.loads(p["body"])
    assert "set_volume" in body["section_title"]
    assert body["markdown"]  # draft included for the reviewer to edit


def test_skill_variant_proposal(store):
    # A->B bigrams close in time.
    import datetime

    base = datetime.datetime.now(datetime.timezone.utc)
    with store._lock:
        for i in range(6):
            for t in ("open_app", "set_volume"):
                ts = (base + datetime.timedelta(seconds=i * 10)).isoformat()
                store._conn.execute(
                    "INSERT INTO skill_runs (ts, tool, args_redacted, "
                    "args_hash, decision, learnable) VALUES (?,?,?,?,?,?)",
                    (ts, t, "{}", "h", "allow", 1),
                )
        store._conn.commit()
    ids = proposer.propose_skill_variants(store, min_evidence=3)
    # Both directions occur (open->set within an iteration, set->open
    # across the iteration boundary) — both are genuine bigrams.
    assert len(ids) == 2
    bodies = [json.loads(store.get_proposal(pid)["body"]) for pid in ids]
    seqs = sorted(json.loads(store.get_proposal(pid)["evidence"])["sequence"] for pid in ids)
    assert seqs == ["open_app -> set_volume", "set_volume -> open_app"]
    by_name = {b["skill_name"]: b for b in bodies}
    assert by_name["learned-open-app-set-volume"]["suggested_tools"] == ["open_app", "set_volume"]


def test_generate_proposals_aggregates(store):
    _run(store, "get_time", "h1", n=3)
    out = proposer.generate_proposals(store, min_evidence=3)
    assert set(out) == {"reflex_rule", "prompt_snippet", "skill_variant"}
    assert len(out["reflex_rule"]) == 1
