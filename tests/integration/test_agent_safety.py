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
    # Task 1.7: audit now lives in audit/YYYY-MM-DD.jsonl (redacted).
    files = sorted((tmp_path / "audit").glob("*.jsonl"))
    assert files, "audit log was not written"
    entries = []
    for f in files:
        entries += [
            json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
    return entries


# ---------------------------------------------------------------------------
# DENY path: blocked, never executed, audited
# ---------------------------------------------------------------------------


def test_deny_does_not_execute(agent, tmp_path):
    with mock.patch.object(agent, "_execute_tool") as m:
        resp = agent._dispatch_tool_call("run_powershell_command", {"command": "Remove-Item C:\\x"})
    assert "Blocked for safety" in resp
    m.assert_not_called()
    assert agent.pending_confirmation is None
    entries = _audit_entries(tmp_path)
    assert entries[-1]["tool"] == "run_powershell_command"
    assert entries[-1]["decision"] == "deny"


def test_deny_dangerous_hotkey(agent):
    with mock.patch.object(agent, "_execute_tool") as m:
        resp = agent._dispatch_tool_call(
            "keyboard_mouse_action", {"action": "press_hotkey", "value": "alt+f4"}
        )
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
        with mock.patch.object(
            AIAgent, "_dispatch_tool_call", side_effect=AssertionError("re-gated!")
        ):
            resp = agent.process("yes")
    assert resp == "done."
    m_exec.assert_called_once_with("system_control", {"action": "empty_recycle_bin"})
    assert agent.pending_confirmation is None


def test_confirm_hinglish_yes_words(agent):
    for word in ["haan", "ok", "go ahead"]:
        agent._dispatch_tool_call("system_control", {"action": "lock_pc"})
        with mock.patch.object(agent, "_execute_tool", return_value="done."):
            with mock.patch.object(
                AIAgent, "_dispatch_tool_call", side_effect=AssertionError("re-gated!")
            ):
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
    agent.pending_confirmation = ("system_control", {"action": "lock_pc"}, time.time() - 9999)
    with mock.patch.object(agent, "_execute_tool") as m:
        resp = agent.process("yes")
    assert "timed out" in resp
    m.assert_not_called()
    assert agent.pending_confirmation is None


def test_confirm_audit_trail(agent, tmp_path):
    agent._dispatch_tool_call("manage_notes", {"action": "clear"})
    with mock.patch.object(agent, "_execute_tool", return_value="cleared."):
        agent.process("yes")
    verdicts = [e["decision"] for e in _audit_entries(tmp_path)]
    assert "confirm_requested" in verdicts
    assert "confirmed" in verdicts


# ---------------------------------------------------------------------------
# ALLOW path: executes and is audited
# ---------------------------------------------------------------------------


def test_allow_executes_and_audits(agent, tmp_path):
    # READ tools auto-execute at the default autonomy level (L1).
    # _execute_tool is mocked: no OS side effects, gate + audit is what's verified.
    with mock.patch.object(agent, "_execute_tool", return_value="ok") as m:
        resp = agent._dispatch_tool_call("web_search", {"query": "test query"})
    assert "Blocked" not in resp
    assert "ACTION_REQUIRES_CONFIRMATION" not in resp
    m.assert_called_once()
    entries = _audit_entries(tmp_path)
    assert entries[-1]["decision"] == "allow"


def test_l1_reversible_needs_confirmation(agent):
    # L1 (default): REVERSIBLE tools confirm instead of auto-executing.
    with mock.patch.object(agent, "_execute_tool") as m:
        resp = agent._dispatch_tool_call("system_control", {"action": "volume_up"})
    assert "ACTION_REQUIRES_CONFIRMATION" in resp
    m.assert_not_called()


# ---------------------------------------------------------------------------
# System prompt carries the safety rules
# ---------------------------------------------------------------------------


def test_system_prompt_has_safety_rules(agent):
    prompt = agent._get_system_prompt()
    assert "non-negotiable" in prompt
    assert "ACTION_REQUIRES_CONFIRMATION" in prompt
    assert "exfiltrate" in prompt
    assert "read-only" in prompt
