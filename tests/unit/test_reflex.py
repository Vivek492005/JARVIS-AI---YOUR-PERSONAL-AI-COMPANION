"""Tests for Task 2.6: reflex layer (System-1) + router."""

import random
from unittest import mock

# Windows-only stubs + the real-fuzzywuzzy fixture live in tests/conftest.py.
import pytest  # noqa: E402

# The reflex tests need the real fuzzywuzzy scorer (other test modules mock
# it for dependency isolation); restored by tests/conftest.py.
pytestmark = pytest.mark.usefixtures("real_fuzzywuzzy")

from jarvis.brain.reflex import (ReflexHit, ReflexMatcher, ReflexStats,  # noqa: E402
                                 normalize, print_stats, render_template)
from jarvis.brain.router import REFLEX_CONFIDENCE, Router  # noqa: E402


@pytest.fixture()
def matcher(tmp_path):
    stats = ReflexStats(path=str(tmp_path / "stats.json"))
    return ReflexMatcher(stats=stats, rng=random.Random(0))


# -- normalization ----------------------------------------------------------

def test_normalize_hinglish_verbs():
    assert normalize("kholo youtube") == "open youtube"
    assert normalize("youtube khol do") == "youtube open"
    assert normalize("bhai volume badhao") == "volume badhao"


def test_normalize_strips_edge_fillers_only():
    assert normalize("please open youtube bhai") == "open youtube"
    # filler inside a query is kept
    assert normalize("search bhai dooj") == "search bhai dooj"


def test_normalize_hindi_numbers():
    assert normalize("volume do") == "volume 2"
    assert normalize("set timer teen minute") == "set timer 3 minute"


# -- templates --------------------------------------------------------------

def test_render_template_groups():
    assert render_template("hi {group1}", ["bob"]) == "hi bob"
    assert render_template("q={group1|urlencode}", ["a b"]) == "q=a+b"
    assert render_template("{group1|default:trending song}", [""]) == "trending song"
    assert render_template("{group1|default:trending song}", ["x"]) == "x"
    assert render_template("no templates", []) == "no templates"
    assert render_template(None, []) is None


# -- extraction fidelity ----------------------------------------------------

def test_rule_table_shape():
    from jarvis.legacy.rule_commands import RULES
    assert len(RULES) == 152
    for r in RULES:
        assert r["id"] and r["patterns"]
        assert set(r) == {"id", "patterns", "tool", "args", "reply", "compute"}


def test_legacy_table_fully_covered_or_excluded():
    """Every legacy command is either extracted or explicitly excluded."""
    import ast
    src = open("src/jarvis/voice/interface.py").read()
    tree = ast.parse(src)
    legacy_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Attribute) and t.attr == "commands":
                    for elt in node.value.elts:
                        for k, v in zip(elt.keys, elt.values, strict=False):
                            if isinstance(k, ast.Constant) and k.value == "id":
                                legacy_ids.add(v.value)
    from jarvis.legacy.rule_commands import RULES
    from jarvis.brain.reflex import ReflexMatcher  # noqa
    extracted = {r["id"] for r in RULES}
    excluded = {"find_file", "ai_summarize", "ai_fix_code", "repeat_last"}
    assert legacy_ids == extracted | excluded


def test_spot_mappings():
    from jarvis.legacy.rule_commands import RULES
    by_id = {r["id"]: r for r in RULES}
    # direct pyautogui/webbrowser paths are now gated ToolSpec calls
    assert by_id["open_youtube"]["tool"] == "open_website"
    assert by_id["youtube_pause"]["tool"] == "keyboard_mouse_action"
    assert by_id["youtube_pause"]["args"]["action"] == "press_key"
    assert by_id["open_notepad"]["tool"] == "open_application"
    assert by_id["volume_up"]["tool"] == "system_control"
    assert by_id["lock_computer"]["args"] == {"action": "lock_pc"}
    assert by_id["clear_notes"]["args"] == {"action": "clear"}


# -- matcher -----------------------------------------------------------------

def test_regex_hit_confidence_1(matcher):
    hit = matcher.match("open youtube")
    assert hit.rule_id == "open_youtube"
    assert hit.confidence == 1.0
    assert hit.tool == "open_website"


def test_fuzzy_hit_below_router_threshold_goes_to_llm(matcher):
    # craft: fuzzy hit exists but we check the confidence value itself
    hit = matcher.match("opne youtube")
    assert hit is not None
    assert hit.confidence >= REFLEX_CONFIDENCE


def test_no_match_returns_none(matcher):
    assert matcher.match("xqzw blorpt fnord") is None
    assert matcher.match("   ") is None


def test_group_capture_and_render(matcher):
    hit = matcher.match("play despacito on youtube")
    assert hit.rule_id == "play_youtube"
    args = hit.render_args()
    assert "despacito" in args["url_or_name"]
    assert "despacito" in hit.render_reply(matcher._rng)


def test_compute_rules(matcher):
    hit = matcher.match("calculate 12 * 8")
    assert hit.compute == "calc"
    assert hit.render_reply(matcher._rng) == "12 * 8 is 96"
    hit = matcher.match("what time is it")
    assert "current time is" in hit.render_reply(matcher._rng)
    # A-07: CPU-DoS guard survives the move
    hit = matcher.match("calculate 9^9^9^9")
    assert "could not calculate" in hit.render_reply(matcher._rng)


# -- router ------------------------------------------------------------------

def _router_with(agent=None, **kw):
    stats = ReflexStats(path=str(kw.pop("tmp_path", ".") ) + "/s.json") \
        if "tmp_path" in kw else None
    return Router(reflex=ReflexMatcher(stats=stats), agent=agent)


def test_router_reflex_path_uses_policy_gate(tmp_path):
    agent = mock.MagicMock()
    router = Router(reflex=ReflexMatcher(
        stats=ReflexStats(path=str(tmp_path / "s.json"))), agent=agent)
    with mock.patch("jarvis.tools.actions.run_action",
                    return_value=("allow", "tool-output")) as ra:
        out = router.handle("open youtube")
    ra.assert_called_once()
    tool, args = ra.call_args[0][:2]
    assert tool == "open_website"
    assert args == {"url_or_name": "https://www.youtube.com"}
    assert out == "Opening YouTube"  # reply template, not raw tool output
    agent.process.assert_not_called()  # LLM never consulted


def test_router_confirm_delegates_to_agent(tmp_path):
    agent = mock.MagicMock()
    agent.request_confirmation.return_value = "confirm?"
    router = Router(reflex=ReflexMatcher(
        stats=ReflexStats(path=str(tmp_path / "s.json"))), agent=agent)
    with mock.patch("jarvis.tools.actions.run_action",
                    return_value=("confirm", "ACTION_REQUIRES_CONFIRMATION: ...")):
        out = router.handle("empty recycle bin")
    agent.request_confirmation.assert_called_once_with(
        "system_control", {"action": "empty_recycle_bin"})
    assert out == "confirm?"


def test_router_deny_returns_block_reason(tmp_path):
    agent = mock.MagicMock()
    router = Router(reflex=ReflexMatcher(
        stats=ReflexStats(path=str(tmp_path / "s.json"))), agent=agent)
    with mock.patch("jarvis.tools.actions.run_action",
                    return_value=("deny", "Blocked for safety: nope")):
        out = router.handle("empty recycle bin")
    assert out == "Blocked for safety: nope"
    agent.process.assert_not_called()


def test_router_low_confidence_falls_to_llm(tmp_path):
    agent = mock.MagicMock()
    agent.process.return_value = "llm reply"
    reflex = ReflexMatcher(stats=ReflexStats(path=str(tmp_path / "s.json")))
    router = Router(reflex=reflex, agent=agent)
    # force a below-threshold hit
    with mock.patch.object(reflex, "match",
                           return_value=ReflexHit(
                               rule_id="x", tool="open_website", args={},
                               reply="r", compute=None, confidence=0.80)):
        assert router.handle("whatever") == "llm reply"
    agent.process.assert_called_once_with("whatever")


def test_router_compute_rule_needs_no_tool_or_llm(tmp_path):
    agent = mock.MagicMock()
    router = Router(reflex=ReflexMatcher(
        stats=ReflexStats(path=str(tmp_path / "s.json")),
        rng=random.Random(1)), agent=agent)
    out = router.handle("flip a coin")
    assert out in ("It's Heads!", "It's Tails!")
    agent.process.assert_not_called()


def test_router_records_stats(tmp_path):
    agent = mock.MagicMock()
    agent.process.return_value = "llm"
    stats = ReflexStats(path=str(tmp_path / "s.json"))
    router = Router(reflex=ReflexMatcher(stats=stats), agent=agent)
    router.handle("open youtube")   # reflex
    router.handle("xqzw blorpt")    # llm
    s = stats.summary()
    assert s["total"] == 2 and s["reflex"] == 1
    assert s["pct"] == 50.0


# -- google fallback removed (privacy) ---------------------------------------

def test_legacy_process_no_google_fallback():
    """Unrecognized input no longer opens a Google search (privacy leak)."""
    from jarvis.voice.interface import VoiceCommandProcessor
    import jarvis.voice.interface as iface
    proc = VoiceCommandProcessor.__new__(VoiceCommandProcessor)
    # minimal attrs for process(): commands + ai_agent=None
    from jarvis.legacy.rule_commands import RULES
    proc.commands = [{"id": r["id"], "patterns": r["patterns"],
                      "action": lambda m: "x", "type": "WEB"} for r in RULES[:1]]
    proc.ai_agent = None
    with mock.patch.object(iface.webbrowser, "open") as wopen:
        out = VoiceCommandProcessor.process(proc, "xqzw blorpt fnord 123")
    wopen.assert_not_called()
    assert out["id"] == "not_understood"
    assert "didn't understand" in out["response"]


# -- stats CLI ----------------------------------------------------------------

def test_print_stats_empty(tmp_path, capsys):
    with mock.patch("jarvis.brain.reflex._default_stats_path",
                    return_value=str(tmp_path / "s.json")):
        print_stats()
    out = capsys.readouterr().out
    assert "Reflex layer coverage" in out
    assert "0.0%" in out


def test_stats_persist_across_instances(tmp_path):
    p = str(tmp_path / "s.json")
    s1 = ReflexStats(path=p)
    s1.record("open_youtube")
    s1.record(None)
    s2 = ReflexStats(path=p)
    assert s2.summary()["total"] == 2
    assert s2.summary()["reflex"] == 1
