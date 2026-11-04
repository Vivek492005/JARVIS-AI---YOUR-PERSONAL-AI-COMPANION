"""Tests for the eval gate (Phase 9 moonshot)."""

import sys

sys.path.insert(0, "src")

from jarvis.learning.eval_gate import run_eval_gate


def _ok_runner(subset):
    cats = {"reflex": (40, 40), "hinglish": (48, 50), "safety": (25, 25),
            "injection": (30, 30), "ambiguity": (15, 15),
            "single-tool": (38, 40), "multi-step": (28, 30)}
    p, t = cats.get(subset, (10, 10))
    return {"passed": p, "total": t,
            "by_category": {subset: {"passed": p, "total": t}}}


def test_gate_passes():
    res = run_eval_gate("reflex_rule", runner=_ok_runner)
    assert res.passed is True
    assert "safety" in res.subsets and "injection" in res.subsets
    assert res.overall_rate >= 0.85


def test_gate_blocks_on_safety_regression():
    def runner(subset):
        out = _ok_runner(subset)
        if subset == "safety":
            out["by_category"]["safety"] = {"passed": 24, "total": 25}
            out["passed"] = 24
        return out
    res = run_eval_gate("reflex_rule", runner=runner)
    assert res.passed is False


def test_gate_blocks_on_low_overall():
    def runner(subset):
        return {"passed": 1, "total": 10,
                "by_category": {subset: {"passed": 1, "total": 10}}}
    # safety/injection missing -> rate None != 1.0 -> fail
    res = run_eval_gate("reflex_rule", runner=runner)
    assert res.passed is False


def test_gate_fail_closed_on_runner_error():
    def runner(subset):
        return {"passed": 0, "total": 0, "by_category": {},
                "error": "timeout"}
    res = run_eval_gate("reflex_rule", runner=runner)
    assert res.passed is False
    assert "timeout" in res.detail


def test_gate_fail_closed_on_exception():
    def runner(subset):
        raise RuntimeError("boom")
    res = run_eval_gate("prompt_snippet", runner=runner)
    assert res.passed is False


def test_subset_mapping_per_type():
    r1 = run_eval_gate("reflex_rule", runner=_ok_runner)
    r2 = run_eval_gate("skill_variant", runner=_ok_runner)
    assert "reflex" in r1.subsets
    assert "multi-step" in r2.subsets
    assert "multi-step" not in r1.subsets
