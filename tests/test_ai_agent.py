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
    # L1 (default autonomy): REVERSIBLE tools confirm instead of auto-run.
    monkeypatch.chdir(tmp_path)
    v, r = run_action("manage_notes",
                      {"action": "save", "content": "Discuss production deployment tomorrow at 10 AM"})
    assert v == "confirm"

    # L2: READ + REVERSIBLE auto-execute — the roundtrip works.
    monkeypatch.setenv("SAFETY__AUTONOMY_LEVEL", "2")
    from access_os.config import reset_settings_cache
    reset_settings_cache()
    try:
        v, r = run_action("manage_notes",
                          {"action": "save", "content": "Discuss production deployment tomorrow at 10 AM"})
        assert v == "allow"
        assert "saved" in r.lower()

        v, r = run_action("manage_notes", {"action": "read"})
        assert v == "allow"
        assert "Discuss production deployment" in r
    finally:
        reset_settings_cache()


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
    """No API keys -> local fallback engine handles note commands.

    The fallback goes through the policy gate (A-01 fix): at the default
    autonomy level (L1) saving a note is REVERSIBLE -> confirmation is
    requested instead of executing blindly.
    """
    monkeypatch.chdir(tmp_path)
    agent = AIAgent()
    assert agent.client is None and agent.backup_client is None
    resp = agent.process("note that remind me to buy milk")
    assert "ACTION_REQUIRES_CONFIRMATION" in resp
    # the pending confirmation resolves on the user's next message
    assert agent.pending_confirmation is not None
    tool, args, _ts = agent.pending_confirmation
    assert tool == "manage_notes" and "milk" in args.get("content", "")


def test_offline_fallback_has_no_destructive_branch(tmp_path, monkeypatch):
    """lock_pc / empty_recycle_bin must NOT be reachable offline (no gate)."""
    monkeypatch.chdir(tmp_path)
    agent = AIAgent()
    resp = agent.process("lock my pc")
    assert "Locking" not in resp  # falls through to web search, not execution
