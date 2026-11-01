"""Tests for Phase 4.1 (agent loop), 4.2 (model router), 4.9 (disambiguation)."""

import sys
from unittest.mock import MagicMock

sys.modules.setdefault("pyautogui", MagicMock(name="pyautogui"))

from jarvis.brain.disambiguate import (
    format_options,
    is_undo_request,
    parse_selection,
)
from jarvis.brain.loop import (
    Action,
    AgentLoop,
    LoopContext,
    LLMPlanner,
    UndoJournal,
    Verifier,
    _parse_action,
    needs_handoff,
)
from jarvis.brain.model_router import (
    CostGuard,
    ModelRouter,
    SemanticCache,
    Tier,
    Usage,
)
from jarvis.brain.providers.base import Completion, ToolCall
from tests.fakes.fake_llm import FakeLLM
from tests.fakes.fake_os import FakeOS


def _planner(script):
    return LLMPlanner(FakeLLM(script=script), system_prompt="test")


class TestActionParsing:
    def test_tool_call(self):
        a = _parse_action('{"type": "tool_call", "tool": "x", "args": {"a": 1}}')
        assert a.type == "tool_call" and a.tool == "x" and a.args == {"a": 1}

    def test_finish(self):
        a = _parse_action('```json\n{"type": "finish", "reply": "done"}\n```')
        assert a.type == "finish" and a.reply == "done"

    def test_invalid(self):
        assert _parse_action("hello world") is None
        assert _parse_action('{"type": "nonsense"}') is None

    def test_repair_loop(self):
        p = _planner([Completion(text='not json at all'),
                      Completion(text='{"type": "finish", "reply": "recovered"}')])
        a = p._ask([{"role": "user", "content": "go"}])
        assert a.reply == "recovered"


class TestAgentLoop:
    def test_happy_path_with_verification(self):
        script = [
            Completion(text='{"type": "finish", "reply": "PLAN: 1) open notepad"}'),
            Completion(text='{"type": "tool_call", "tool": "open_application", '
                            '"args": {"app_name": "notepad"}}'),
            Completion(text='{"type": "finish", "reply": "Ho gaya: Notepad khol diya"}'),
        ]
        # open_application is REVERSIBLE -> CONFIRM at L1; accept it.
        loop = AgentLoop(_planner(script), max_steps=6, wall_time_s=30,
                         confirm_callback=lambda t, a: True)
        with FakeOS():
            out = loop.run_task("notepad kholo", LoopContext())
        assert "Ho gaya" in out

    def test_unknown_tool_goes_back_to_planner(self):
        script = [
            Completion(text='{"type": "finish", "reply": "PLAN: 1) x"}'),
            Completion(text='{"type": "tool_call", "tool": "nope", "args": {}}'),
            Completion(text='{"type": "finish", "reply": "wapas aaya"}'),
        ]
        loop = AgentLoop(_planner(script), max_steps=6, wall_time_s=30)
        out = loop.run_task("kuch karo", LoopContext())
        assert "wapas aaya" in out

    def test_step_limit(self):
        script = [Completion(text='{"type": "tool_call", "tool": "web_search", '
                                   '"args": {"query": "x"}}')] * 20
        loop = AgentLoop(_planner(script), max_steps=3, wall_time_s=30)
        with FakeOS():
            out = loop.run_task("khojo", LoopContext())
        assert "Step limit" in out

    def test_kill_switch(self):
        from jarvis.core.safety import KillSwitch
        ks = KillSwitch()
        ks.trigger("test")
        script = [Completion(text='{"type": "finish", "reply": "PLAN: 1) x"}')]
        loop = AgentLoop(_planner(script), kill_switch=ks)
        assert "Rok diya" in loop.run_task("karo", LoopContext())

    def test_confirm_decline_continues(self):
        script = [
            Completion(text='{"type": "finish", "reply": "PLAN: 1) x"}'),
            Completion(text='{"type": "tool_call", "tool": "system_control", '
                            '"args": {"action": "empty_recycle_bin"}}'),
            Completion(text='{"type": "finish", "reply": "theek hai, cancel"}'),
        ]
        loop = AgentLoop(_planner(script), max_steps=6, wall_time_s=30,
                         confirm_callback=lambda t, a: False)
        with FakeOS():
            out = loop.run_task("recycle bin khaali karo", LoopContext())
        assert "cancel" in out

    def test_handoff_on_login(self):
        script = [
            Completion(text='{"type": "finish", "reply": "PLAN: 1) x"}'),
            Completion(text='{"type": "tool_call", "tool": "web_search", '
                            '"args": {"query": "bank"}}'),
        ]
        loop = AgentLoop(_planner(script), max_steps=6, wall_time_s=30)
        with FakeOS(results={"web_search": "please log in to continue"}):
            out = loop.run_task("bank khojo", LoopContext())
        assert "Aap" in out  # handoff message


class TestVerifier:
    def test_open_application_failure_detected(self):
        v = Verifier()
        ok, ev = v.verify("open_application", {"app_name": "x"},
                          "Could not launch x")
        assert not ok

    def test_unknown_tool_heuristic(self):
        v = Verifier()
        ok, ev = v.verify("mystery", {}, "result text")
        assert ok  # heuristic pass, never false certainty of failure


class TestUndoJournal:
    def test_record_and_undo(self):
        uj = UndoJournal()
        uj.record("system_control", {"action": "mute"}, "muted")
        assert len(uj) == 1
        msg = uj.undo_last(lambda t, a: f"ran {t}")
        assert "Wapas kar diya" in msg and len(uj) == 0

    def test_empty(self):
        assert "kuch nahi" in UndoJournal().undo_last(lambda t, a: "")

    def test_non_reversible_not_recorded(self):
        uj = UndoJournal()
        uj.record("web_search", {"query": "x"}, "ok")
        assert len(uj) == 0

    def test_needs_handoff(self):
        assert needs_handoff("please log in") is not None
        assert needs_handoff("captcha required") is not None
        assert needs_handoff("opened chrome") is None


class TestModelRouter:
    def test_t1_default(self):
        assert ModelRouter().route("chrome kholo").tier == Tier.T1_FAST

    def test_t2_signals(self):
        r = ModelRouter()
        assert r.route("detailed plan banao with steps").tier == Tier.T2_STRONG
        assert r.route("notepad kholo aur phir usme likho meeting notes").tier == Tier.T2_STRONG

    def test_t3_offline(self):
        r = ModelRouter().route("khol do", {"offline": True})
        assert r.tier == Tier.T3_LOCAL

    def test_config_models_not_hardcoded(self):
        s = type("S", (), {"brain": type("B", (), {
            "t1_model": "my-fast", "t2_model": "my-strong", "t3_model": "my-local"})()})()
        r = ModelRouter(s)
        assert r.route("hi").model == "my-fast"
        assert r.route("banao detailed plan abhi").model == "my-strong"


class TestCostGuard:
    def _settings(self, tok, inr):
        return type("S", (), {"brain": type("B", (), {
            "daily_token_budget": tok, "daily_cost_inr_budget": inr})()})()

    def test_breach_downgrades(self):
        notes = []
        cg = CostGuard(self._settings(10, 0), notify=notes.append)
        cg.record(Usage(prompt_tokens=11))
        assert cg.breached and notes
        assert cg.effective_tier(Tier.T2_STRONG) == Tier.T1_FAST
        assert cg.effective_tier(Tier.T1_FAST) == Tier.T1_FAST

    def test_no_budget_no_breach(self):
        cg = CostGuard(self._settings(0, 0))
        cg.record(Usage(prompt_tokens=10**9))
        assert not cg.breached


class TestSemanticCache:
    def test_hit_and_miss(self):
        sc = SemanticCache(ttl_s=60)
        assert sc.get("q") is None
        sc.put("q", "a", involved_tools=False)
        assert sc.get("q") == "a"

    def test_never_caches_tool_calls(self):
        sc = SemanticCache()
        sc.put("q", "a", involved_tools=True)
        assert sc.get("q") is None

    def test_ttl_expiry(self):
        sc = SemanticCache(ttl_s=-1)
        sc.put("q", "a", involved_tools=False)
        assert sc.get("q") is None


class TestDisambiguation:
    def test_format(self):
        out = format_options("Kaunsa?", ["a.pdf", "b.pdf"])
        assert "1) a.pdf" in out and "2) b.pdf" in out

    def test_numbers(self):
        assert parse_selection("2", 3) == 1
        assert parse_selection("5", 3) is None

    def test_ordinals(self):
        assert parse_selection("pehla wala", 3) == 0
        assert parse_selection("dusra", 3) == 1
        assert parse_selection("akhri", 3) == 2

    def test_undo_request(self):
        assert is_undo_request("wapas kar do")
        assert not is_undo_request("chrome kholo")
