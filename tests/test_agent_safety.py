"""
Tests for the Plan-01 safety wiring in access_os/ai_agent.py:
policy-gated dispatch, the confirm-before-destroy flow, and the audit trail.

Needs the `openai` package importable (AIAgent imports it lazily for client
setup) but no API keys and no network. Run with:
    python -m pytest tests/test_agent_safety.py -v
"""

import json
import time
from unittest import mock

import pytest

from access_os.ai_agent import AIAgent


@pytest.fixture
def agent(tmp_path, monkeypatch):
    # Keep audit logs / notes out of the real repo dir.
    monkeypatch.chdir(tmp_path)
    return AIAgent()


def _audit_entries(tmp_path):
    log = tmp_path / "jarvis_audit.log"
    assert log.exists(), "audit log was not written"
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------------
# DENY path: blocked, never executed, audited
# ---------------------------------------------------------------------------

def test_deny_does_not_execute(agent, tmp_path):
    with mock.patch.object(agent, "_execute_tool") as m:
        resp = agent._dispatch_tool_call(
            "run_powershell_command", {"command": "Remove-Item C:\\x"})
    assert "Blocked for safety" in resp
    m.assert_not_called()
    assert agent.pending_confirmation is None
    entries = _audit_entries(tmp_path)
    assert entries[-1]["tool"] == "run_powershell_command"
    assert entries[-1]["verdict"] == "deny"


def test_deny_dangerous_hotkey(agent):
    with mock.patch.object(agent, "_execute_tool") as m:
        resp = agent._dispatch_tool_call(
            "keyboard_mouse_action", {"action": "press_hotkey", "value": "alt+f4"})
    assert "Blocked for safety" in resp
    m.assert_not_called()


# ---------------------------------------------------------------------------
# CONFIRM path: stored, then resolved by the user's next message
# ---------------------------------------------------------------------------

def test_confirm_stores_pending(agent):
    resp = agent._dispatch_tool_call("system_control", {"action": "empty_recycle_bin"})
    assert "ACTION_REQUIRES_CONFIRMATION" in resp
    assert "Recycle Bin" in resp
    name, args, _ts = agent.pending_confirmation
    assert name == "system_control"
    assert args["action"] == "empty_recycle_bin"


def test_confirm_yes_executes_exactly_once_without_regating(agent):
    agent._dispatch_tool_call("system_control", {"action": "empty_recycle_bin"})
    with mock.patch.object(agent, "_execute_tool", return_value="done.") as m_exec:
        # If the confirmation path ever re-gates through _dispatch_tool_call,
        # it would loop forever asking for confirmation — fail loudly.
        with mock.patch.object(AIAgent, "_dispatch_tool_call",
                               side_effect=AssertionError("re-gated!")):
            resp = agent.process("yes")
    assert resp == "done."
    m_exec.assert_called_once_with("system_control", {"action": "empty_recycle_bin"})
    assert agent.pending_confirmation is None


def test_confirm_hinglish_yes_words(agent):
    for word in ["haan", "ok", "go ahead"]:
        agent._dispatch_tool_call("system_control", {"action": "lock_pc"})
        with mock.patch.object(agent, "_execute_tool", return_value="done."):
            with mock.patch.object(AIAgent, "_dispatch_tool_call",
                                   side_effect=AssertionError("re-gated!")):
                agent.process(word)
        assert agent.pending_confirmation is None, word


def test_confirm_no_cancels(agent):
    agent._dispatch_tool_call("system_control", {"action": "lock_pc"})
    with mock.patch.object(agent, "_execute_tool") as m:
        resp = agent.process("nahi rehne do")
    assert "Cancelled" in resp
    m.assert_not_called()
    assert agent.pending_confirmation is None


def test_confirm_timeout_cancels(agent):
    agent.pending_confirmation = (
        "system_control", {"action": "lock_pc"}, time.time() - 9999)
    with mock.patch.object(agent, "_execute_tool") as m:
        resp = agent.process("yes")
    assert "timed out" in resp
    m.assert_not_called()
    assert agent.pending_confirmation is None


def test_confirm_audit_trail(agent, tmp_path):
    agent._dispatch_tool_call("manage_notes", {"action": "clear"})
    with mock.patch.object(agent, "_execute_tool", return_value="cleared."):
        agent.process("yes")
    verdicts = [e["verdict"] for e in _audit_entries(tmp_path)]
    assert "confirm_requested" in verdicts
    assert "confirmed" in verdicts


# ---------------------------------------------------------------------------
# ALLOW path: executes and is audited
# ---------------------------------------------------------------------------

def test_allow_executes_and_audits(agent, tmp_path):
    # volume_up needs pyautogui (absent here) — the executor catches that and
    # returns an error string; the gate + audit path is what we verify.
    resp = agent._dispatch_tool_call("system_control", {"action": "volume_up"})
    assert "Blocked" not in resp
    assert "ACTION_REQUIRES_CONFIRMATION" not in resp
    entries = _audit_entries(tmp_path)
    assert entries[-1]["verdict"] == "allow"


# ---------------------------------------------------------------------------
# System prompt carries the safety rules
# ---------------------------------------------------------------------------

def test_system_prompt_has_safety_rules(agent):
    prompt = agent._get_system_prompt()
    assert "non-negotiable" in prompt
    assert "ACTION_REQUIRES_CONFIRMATION" in prompt
    assert "exfiltrate" in prompt
    assert "read-only" in prompt
