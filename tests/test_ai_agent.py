"""
Smoke tests for the JARVIS AI Agent & unified action pipeline (Phase C).

Uses the single action home (access_os/actions.py) via run_action().
No API keys, no network, no Windows required.
"""

import sys
import os

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_TEST_DIR)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from access_os.actions import run_action, execute_tool_raw
from access_os.ai_agent import AIAgent


def test_notes_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v, r = run_action("manage_notes",
                      {"action": "save", "content": "Discuss production deployment tomorrow at 10 AM"})
    assert v == "allow"
    assert "saved" in r.lower()

    v, r = run_action("manage_notes", {"action": "read"})
    assert v == "allow"
    assert "Discuss production deployment" in r


def test_clear_notes_requires_confirmation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v, r = run_action("manage_notes", {"action": "clear"})
    assert v == "confirm"
    assert "ACTION_REQUIRES_CONFIRMATION" in r


def test_destructive_blocked_in_legacy_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v, r = run_action("run_powershell_command", {"command": "Remove-Item C:\\x"})
    assert v == "deny"
    assert "Blocked for safety" in r


def test_offline_fallback_note(tmp_path, monkeypatch):
    """No API keys -> local fallback engine handles note commands."""
    monkeypatch.chdir(tmp_path)
    agent = AIAgent()
    assert agent.client is None and agent.backup_client is None
    resp = agent.process("note that remind me to buy milk")
    assert "milk" in resp.lower()


def test_offline_fallback_has_no_destructive_branch(tmp_path, monkeypatch):
    """lock_pc / empty_recycle_bin must NOT be reachable offline (no gate)."""
    monkeypatch.chdir(tmp_path)
    agent = AIAgent()
    resp = agent.process("lock my pc")
    assert "Locking" not in resp  # falls through to web search, not execution
