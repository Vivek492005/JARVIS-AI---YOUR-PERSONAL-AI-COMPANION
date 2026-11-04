"""
Tests for Phase C unification: the legacy regex engine delegates to the
shared action home (access_os/actions.py) through the policy gate.

Heavy optional deps (speech_recognition, pyttsx3, pyautogui, pyperclip) are
stubbed so these tests run anywhere without a microphone, camera or Windows.
"""

import sys
import time
from unittest import mock

import pytest

# --- stub heavy modules BEFORE importing voice_interface --------------------
for _mod in ["speech_recognition", "pyttsx3", "pyautogui", "pyperclip", "fuzzywuzzy"]:
    sys.modules.setdefault(_mod, mock.MagicMock())
_fz = sys.modules["fuzzywuzzy"]
if not hasattr(_fz, "fuzz"):
    _fz.fuzz = mock.MagicMock()

from access_os.voice_interface import VoiceCommandProcessor, CommandType  # noqa: E402


class FakeAgent:
    """Minimal stand-in for AIAgent's confirmation surface."""

    def __init__(self):
        self.pending_confirmation = None
        self.process_seen = []

    def process(self, text):
        self.process_seen.append(text)
        return "fake-agent-result"

    def request_confirmation(self, tool_name, args):
        self.pending_confirmation = (tool_name, args, time.time())
        return "ACTION_REQUIRES_CONFIRMATION: please confirm"


class FakeMatch:
    def __init__(self, *groups):
        self._groups = groups

    def group(self, n):
        return self._groups[n - 1]

    def groups(self):
        return self._groups


@pytest.fixture
def proc(tmp_path):
    p = VoiceCommandProcessor(notes_file=str(tmp_path / "notes.txt"))
    p.ai_agent = FakeAgent()
    return p


# ---------------------------------------------------------------------------
# 0. Pending confirmations take precedence in process()
# ---------------------------------------------------------------------------


def test_process_delegates_pending_confirmation(proc):
    proc.ai_agent.pending_confirmation = ("system_control", {"action": "lock_pc"}, time.time())
    out = proc.process("yes")
    assert out["id"] == "confirm_flow"
    assert out["type"] == CommandType.AI
    assert out["response"] == "fake-agent-result"
    assert proc.ai_agent.process_seen == ["yes"]


def test_process_normal_routing_when_no_pending(proc):
    # "what time is it" hits the regex layer, not the agent.
    out = proc.process("what time is it")
    assert out["id"] != "confirm_flow"
    assert "time" in out["response"].lower()


# ---------------------------------------------------------------------------
# _gated(): ALLOW / CONFIRM / DENY handling in the legacy path
# ---------------------------------------------------------------------------


def test_gated_confirm_registers_on_agent(proc):
    with mock.patch(
        "access_os.voice_interface.run_action",
        return_value=("confirm", "ACTION_REQUIRES_CONFIRMATION: q"),
    ):
        resp = proc._action_lock_pc()
    assert "ACTION_REQUIRES_CONFIRMATION" in resp
    assert proc.ai_agent.pending_confirmation is not None
    assert proc.ai_agent.pending_confirmation[0] == "system_control"


def test_gated_confirm_without_agent_cancels_safely(tmp_path):
    p = VoiceCommandProcessor(notes_file=str(tmp_path / "notes.txt"))
    p.ai_agent = None
    with mock.patch(
        "access_os.voice_interface.run_action",
        return_value=("confirm", "ACTION_REQUIRES_CONFIRMATION: q"),
    ):
        resp = p._action_empty_recycle_bin()
    assert "cancelled" in resp.lower()


def test_gated_deny_returns_reason(proc):
    with mock.patch(
        "access_os.voice_interface.run_action", return_value=("deny", "Blocked for safety: nope")
    ):
        resp = proc._action_lock_pc()
    assert "Blocked for safety" in resp
    assert proc.ai_agent.pending_confirmation is None


def test_gated_allow_uses_ok_msg(proc):
    with mock.patch("access_os.voice_interface.run_action", return_value=("allow", "raw result")):
        resp = proc._action_lock_pc()
    assert resp == "Locking the workstation"


# ---------------------------------------------------------------------------
# Adapters call the right tools with the right args
# ---------------------------------------------------------------------------


def test_adapter_routes_through_run_action(proc):
    seen = {}

    def fake_run(tool, args, notes_file=None):
        seen["tool"] = tool
        seen["args"] = args
        return ("allow", "ok")

    with mock.patch("access_os.voice_interface.run_action", side_effect=fake_run):
        proc._action_take_note(FakeMatch("buy milk"))
        assert seen["tool"] == "manage_notes"
        assert seen["args"] == {"action": "save", "content": "buy milk"}

        proc._action_type_text(FakeMatch("hello world"))
        assert seen["tool"] == "keyboard_mouse_action"
        assert seen["args"] == {"action": "type_text", "value": "hello world"}

        proc._action_check_battery()
        assert seen["tool"] == "system_control"
        assert seen["args"] == {"action": "check_battery"}
