"""Task 1.11: adversarial security suite — unregistered tools.

An unknown tool name must be rejected at EVERY entry point, never executed.
"""

import sys
from unittest import mock
from unittest.mock import MagicMock

for _mod in ("speech_recognition", "pyttsx3", "pyautogui", "pyperclip", "fuzzywuzzy"):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))
sys.modules["fuzzywuzzy"].fuzz = MagicMock()

import pytest  # noqa: E402

from access_os.actions import execute_tool_raw, run_action  # noqa: E402
from access_os.ai_agent import AIAgent  # noqa: E402
from access_os.policy import Decision, PolicyContext, decide_tool_call  # noqa: E402
from access_os.tools.registry import resolve  # noqa: E402

BOGUS = [
    "delete_everything",
    "rm",
    "exec",
    "system",
    "eval",
    "keyboard_mouse_action ",
    " web_search",
    "WEB_SEARCH",
    "",
    "None",
    "null",
]


@pytest.mark.parametrize("name", BOGUS)
def test_registry_rejects(name):
    assert resolve(name, {}) is None


@pytest.mark.parametrize("name", BOGUS)
def test_policy_denies(name):
    d, reason = decide_tool_call(name, {}, PolicyContext(), level=3)
    assert d == Decision.DENY


@pytest.mark.parametrize("name", BOGUS)
def test_execute_raw_rejects(name):
    r = execute_tool_raw(name, {})
    assert "not recognized" in r


@pytest.mark.parametrize("name", BOGUS)
def test_run_action_rejects(name):
    v, r = run_action(name, {})
    assert v == "deny"


def test_dispatch_rejects_and_audits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = AIAgent()
    with mock.patch.object(agent, "_execute_tool") as m:
        r = agent._dispatch_tool_call("delete_everything", {})
    m.assert_not_called()
    assert "not recognized" in r or "Blocked" in r


def test_case_sensitivity_is_deny_not_execute():
    # "WEB_SEARCH" must not resolve to web_search — fail closed.
    assert resolve("WEB_SEARCH", {"query": "x"}) is None
    d, _ = decide_tool_call("WEB_SEARCH", {"query": "x"}, level=3)
    assert d == Decision.DENY
