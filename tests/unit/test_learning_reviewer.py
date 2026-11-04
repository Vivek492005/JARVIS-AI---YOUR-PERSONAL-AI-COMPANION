"""Tests for the proposal reviewer (Phase 9 moonshot).

Covers: payload validation (fail-closed), eval-gated approve, reject/edit,
revert, and the capability cap (learned rules can never target
DESTRUCTIVE/SYSTEM tools).
"""

import json
import sys

import pytest
from pydantic import BaseModel

sys.path.insert(0, "src")

from jarvis.learning.reviewer import Reviewer
from jarvis.learning.store import LearningStore
from jarvis.tools.registry import REGISTRY, Risk, ToolSpec


class _NoParams(BaseModel):
    pass


def _register(name, risk):
    spec = ToolSpec(
        name=name,
        description="test tool",
        params=_NoParams,
        risk=risk,
        handler=lambda args, cb, nf: "ok",
    )
    REGISTRY[name] = spec
    return spec


@pytest.fixture()
def tools():
    names = []
    for n, r in (
        ("learn_test_read", Risk.READ),
        ("learn_test_rev", Risk.REVERSIBLE),
        ("learn_test_des", Risk.DESTRUCTIVE),
    ):
        _register(n, r)
        names.append(n)
    yield names
    for n in names:
        REGISTRY.pop(n, None)


@pytest.fixture()
def store(tmp_path):
    s = LearningStore(tmp_path / "learning.db")
    yield s
    s.close()


@pytest.fixture()
def reviewer(store, tmp_path):
    return Reviewer(
        store,
        learned_rules_path=tmp_path / "reflex_learned.json",
        learned_prompt_path=tmp_path / "learned.md",
        skills_dir=tmp_path / "skills",
    )


def _ok_runner(subset):
    return {
        "passed": 10,
        "total": 10,
        "by_category": {
            subset: {"passed": 10, "total": 10},
            "safety": {"passed": 5, "total": 5},
            "injection": {"passed": 5, "total": 5},
        },
    }


def _fail_runner(subset):
    return {
        "passed": 1,
        "total": 10,
        "by_category": {
            subset: {"passed": 1, "total": 10},
            "safety": {"passed": 5, "total": 5},
            "injection": {"passed": 5, "total": 5},
        },
    }


def _mk(store, ptype, body, target="t"):
    return store.add_proposal(ptype, target, f"{ptype} proposal", body, {"n": 3}, 0.7)


# -- reflex_rule ------------------------------------------------------------


def test_approve_reflex_rule_happy_path(reviewer, store, tools, tmp_path):
    body = {
        "rule": {
            "id": "learned_learn_test_read_ab12cd34",
            "patterns": ["^what time is it$"],
            "tool": "learn_test_read",
            "args": {},
            "reply": "time",
        }
    }
    pid = _mk(store, "reflex_rule", body)
    out = reviewer.approve(pid, eval_runner=_ok_runner)
    assert out.ok, out.message
    assert out.applied_id is not None
    assert store.get_proposal(pid)["status"] == "applied"
    rules = json.loads((tmp_path / "reflex_learned.json").read_text())
    assert len(rules) == 1
    assert rules[0]["id"] == "learned_learn_test_read_ab12cd34"
    # Backup recorded for revert.
    rec = store.get_applied(out.applied_id)
    assert json.loads(rec["backup"]) == {"previous": []}


def test_reflex_rule_refuses_empty_patterns(reviewer, store, tools):
    body = {"rule": {"id": "learned_x", "patterns": [], "tool": "learn_test_read", "args": {}}}
    pid = _mk(store, "reflex_rule", body)
    out = reviewer.approve(pid, eval_runner=_ok_runner)
    assert not out.ok
    assert "pattern" in out.message
    assert store.get_proposal(pid)["status"] == "pending"


def test_reflex_rule_refuses_destructive_tool(reviewer, store, tools):
    # The capability cap: a learned regex must never bypass confirmation.
    body = {
        "rule": {
            "id": "learned_learn_test_des_ab12cd34",
            "patterns": ["^delete everything$"],
            "tool": "learn_test_des",
            "args": {},
        }
    }
    pid = _mk(store, "reflex_rule", body)
    out = reviewer.approve(pid, eval_runner=_ok_runner)
    assert not out.ok
    assert "DESTRUCTIVE" in out.message


def test_reflex_rule_refuses_unknown_tool(reviewer, store):
    body = {
        "rule": {
            "id": "learned_nope_ab12cd34",
            "patterns": ["^x$"],
            "tool": "no_such_tool",
            "args": {},
        }
    }
    pid = _mk(store, "reflex_rule", body)
    out = reviewer.approve(pid, eval_runner=_ok_runner)
    assert not out.ok
    assert "unknown tool" in out.message


def test_reflex_rule_refuses_bad_regex(reviewer, store, tools):
    body = {
        "rule": {
            "id": "learned_learn_test_read_ab12cd34",
            "patterns": ["^([unclosed$"],
            "tool": "learn_test_read",
            "args": {},
        }
    }
    pid = _mk(store, "reflex_rule", body)
    out = reviewer.approve(pid, eval_runner=_ok_runner)
    assert not out.ok
    assert "does not compile" in out.message


def test_approve_blocked_by_eval_gate(reviewer, store, tools):
    body = {
        "rule": {
            "id": "learned_learn_test_read_ab12cd34",
            "patterns": ["^hi$"],
            "tool": "learn_test_read",
            "args": {},
        }
    }
    pid = _mk(store, "reflex_rule", body)
    out = reviewer.approve(pid, eval_runner=_fail_runner)
    assert not out.ok
    assert "eval gate FAILED" in out.message
    # Fail-closed: still pending, nothing written, report attached.
    assert store.get_proposal(pid)["status"] == "pending"
    rep = json.loads(store.get_proposal(pid)["eval_report"])
    assert rep["passed"] is False


# -- prompt_snippet ----------------------------------------------------------


def test_approve_prompt_snippet(reviewer, store, tmp_path):
    body = {"section_title": "Learned: get_time", "markdown": "**get_time**: be careful."}
    pid = _mk(store, "prompt_snippet", body)
    out = reviewer.approve(pid, eval_runner=_ok_runner)
    assert out.ok, out.message
    text = (tmp_path / "learned.md").read_text(encoding="utf-8")
    assert "## Learned: get_time" in text
    assert pid in text  # provenance marker


def test_prompt_snippet_rejects_script(reviewer, store):
    body = {"section_title": "x", "markdown": "<script>alert(1)</script>"}
    pid = _mk(store, "prompt_snippet", body)
    out = reviewer.approve(pid, eval_runner=_ok_runner)
    assert not out.ok


# -- skill_variant ------------------------------------------------------------


def test_approve_skill_variant(reviewer, store, tmp_path):
    body = {
        "skill_name": "learned-open-then-mute",
        "description": "composite",
        "suggested_tools": ["open_app", "set_volume"],
    }
    pid = _mk(store, "skill_variant", body)
    out = reviewer.approve(pid, eval_runner=_ok_runner)
    assert out.ok, out.message
    d = tmp_path / "skills" / "learned-open-then-mute"
    assert (d / "SKILL.md").exists()
    assert "composite" in (d / "SKILL.md").read_text(encoding="utf-8")
    # Scaffold is inert: tool.py has no UNCOMMENTED registration
    # (register_skill_tool appears only in comments).
    code_lines = [
        line
        for line in (d / "tool.py").read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert not any("register_skill_tool(" in line for line in code_lines)


def test_skill_variant_refuses_existing_dir(reviewer, store, tmp_path):
    (tmp_path / "skills" / "learned-dup").mkdir(parents=True)
    body = {"skill_name": "learned-dup", "description": "x", "suggested_tools": []}
    pid = _mk(store, "skill_variant", body)
    out = reviewer.approve(pid, eval_runner=_ok_runner)
    assert not out.ok
    assert "already exists" in out.message


# -- reject / edit / revert -----------------------------------------------------


def test_reject_and_edit(reviewer, store):
    pid = _mk(store, "prompt_snippet", {"section_title": "t", "markdown": "m"})
    out = reviewer.edit(pid, title="new title")
    assert out.ok
    assert store.get_proposal(pid)["title"] == "new title"
    out = reviewer.reject(pid, reason="not useful")
    assert out.ok
    assert store.get_proposal(pid)["status"] == "rejected"
    # Can't approve a rejected proposal.
    out = reviewer.approve(pid, eval_runner=_ok_runner)
    assert not out.ok


def test_edit_revalidates_payload(reviewer, store):
    pid = _mk(store, "prompt_snippet", {"section_title": "t", "markdown": "m"})
    out = reviewer.edit(pid, body={"section_title": "", "markdown": ""})
    assert not out.ok  # empty title rejected by validator


def test_revert_reflex_rule(reviewer, store, tools, tmp_path):
    body = {
        "rule": {
            "id": "learned_learn_test_rev_ab12cd34",
            "patterns": ["^mute$"],
            "tool": "learn_test_rev",
            "args": {},
        }
    }
    pid = _mk(store, "reflex_rule", body)
    out = reviewer.approve(pid, eval_runner=_ok_runner)
    assert out.ok
    rev = reviewer.revert(out.applied_id)
    assert rev.ok, rev.message
    rules = json.loads((tmp_path / "reflex_learned.json").read_text())
    assert rules == []
    assert store.get_proposal(pid)["status"] == "reverted"


def test_revert_skill_variant_removes_dir(reviewer, store, tmp_path):
    body = {"skill_name": "learned-tmp-skill", "description": "x", "suggested_tools": []}
    pid = _mk(store, "skill_variant", body)
    out = reviewer.approve(pid, eval_runner=_ok_runner)
    assert out.ok
    assert (tmp_path / "skills" / "learned-tmp-skill").exists()
    assert reviewer.revert(out.applied_id).ok
    assert not (tmp_path / "skills" / "learned-tmp-skill").exists()


def test_double_approve_refused(reviewer, store, tools):
    body = {
        "rule": {
            "id": "learned_learn_test_read_zz99yy88",
            "patterns": ["^yo$"],
            "tool": "learn_test_read",
            "args": {},
        }
    }
    pid = _mk(store, "reflex_rule", body)
    assert reviewer.approve(pid, eval_runner=_ok_runner).ok
    out = reviewer.approve(pid, eval_runner=_ok_runner)
    assert not out.ok
    assert "not pending" in out.message
