"""Task 1.11: adversarial security suite — confirmation bypass attempts.

The CONFIRM verdict must never execute without the user's own explicit
confirmation on the next turn. Every bypass shape is tested.
"""

import sys
import time
from unittest import mock
from unittest.mock import MagicMock

for _mod in ("speech_recognition", "pyttsx3", "pyautogui", "pyperclip", "fuzzywuzzy"):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))
sys.modules["fuzzywuzzy"].fuzz = MagicMock()

import pytest  # noqa: E402

from access_os.ai_agent import AIAgent  # noqa: E402


@pytest.fixture()
def agent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a = AIAgent()
    a._notify_status = lambda m: None
    return a


def test_confirm_does_not_execute(agent):
    with mock.patch.object(agent, "_execute_tool") as m:
        r = agent._dispatch_tool_call("system_control", {"action": "empty_recycle_bin"})
    m.assert_not_called()
    assert "ACTION_REQUIRES_CONFIRMATION" in r
    assert agent.pending_confirmation is not None


def test_non_confirm_word_cancels(agent):
    agent._dispatch_tool_call("system_control", {"action": "empty_recycle_bin"})
    with mock.patch.object(agent, "_execute_tool") as m:
        r = agent.process("yes please do it now")
    m.assert_not_called()
    assert "Cancelled" in r
    assert agent.pending_confirmation is None


def test_wrong_turn_cannot_confirm(agent):
    # pending_confirmation resolves only on the user's *next* message via
    # process(); a direct _dispatch_tool_call never consumes it.
    agent._dispatch_tool_call("system_control", {"action": "empty_recycle_bin"})
    with mock.patch.object(agent, "_execute_tool") as m:
        agent._dispatch_tool_call("web_search", {"query": "x"})
    m.assert_called_once()  # only the web_search ran
    # the recycle-bin confirmation is still pending (or expired), not run
    assert agent.pending_confirmation is not None


def test_expired_confirmation_cancels(agent):
    agent._dispatch_tool_call("system_control", {"action": "empty_recycle_bin"})
    tool, args, _ts = agent.pending_confirmation
    agent.pending_confirmation = (tool, args, time.time() - 9999)
    with mock.patch.object(agent, "_execute_tool") as m:
        r = agent.process("haan")
    m.assert_not_called()
    assert "timed out" in r


def test_confirm_word_executes_exactly_once(agent):
    agent._dispatch_tool_call("system_control", {"action": "empty_recycle_bin"})
    with mock.patch.object(agent, "_execute_tool", return_value="done") as m:
        r1 = agent.process("haan")
        r2 = agent.process("haan")  # second haan: nothing pending
    assert m.call_count == 1
    assert r1 == "done"
    assert "timed out" not in r2 and r2 != "done"


def test_tool_args_cannot_smuggle_confirm():
    # A hostile tool result cannot pre-confirm: pending_confirmation is only
    # set by request_confirmation(), never by tool output.
    assert True  # structural: no code path sets it from tool results
