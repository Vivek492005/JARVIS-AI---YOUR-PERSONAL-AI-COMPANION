"""Task 1.11: adversarial security suite — foreground-guard bypass attempts.

The Task 1.4 guard must hold against action-name smuggling, case tricks,
and unknown actions (which must fail closed, not bypass the guard).
"""

import sys
from unittest.mock import MagicMock

for _mod in ("pyautogui", "pyperclip"):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))

import pytest  # noqa: E402

from access_os import actions as A  # noqa: E402
from access_os.policy import Decision, decide_tool_call  # noqa: E402


@pytest.fixture()
def terminal_fg(monkeypatch):
    monkeypatch.setattr(A, "get_foreground_process",
                        lambda: "powershell.exe")


@pytest.mark.parametrize("action", ["type_text", "press_key", "press_hotkey"])
def test_guard_blocks_all_keystroke_actions(terminal_fg, action):
    r = A.keyboard_mouse_action(action, "x")
    assert r.startswith("Blocked for safety")


@pytest.mark.parametrize("action", ["TYPE_TEXT", "Type_Text", "type text",
                                    "type_text ", "press_hotkey "])
def test_case_and_spacing_tricks_fail_closed(terminal_fg, action):
    # Unknown action spellings must NOT execute keystrokes — the executor
    # only handles exact names and reports unknown otherwise.
    r = A.keyboard_mouse_action(action, "ctrl+s")
    assert "Pressed" not in r and "Typed" not in r


def test_guard_message_names_process(terminal_fg):
    r = A.keyboard_mouse_action("type_text", "hello")
    assert "powershell.exe" in r


def test_non_terminal_still_gated_by_policy(monkeypatch):
    # Guard open (notepad) — the policy tier still governs the call.
    monkeypatch.setattr(A, "get_foreground_process", lambda: "notepad.exe")
    d, _ = decide_tool_call("keyboard_mouse_action",
                            {"action": "type_text", "value": "hi"}, level=1)
    assert d == Decision.CONFIRM  # REVERSIBLE at L1


def test_unknown_foreground_is_not_a_bypass(monkeypatch):
    # get_foreground_process() -> None (Linux / Win32 failed): guard passes
    # open, but nothing about the policy changes.
    monkeypatch.setattr(A, "get_foreground_process", lambda: None)
    r = A.keyboard_mouse_action("type_text", "hi")
    assert not r.startswith("Blocked")
    d, _ = decide_tool_call("keyboard_mouse_action",
                            {"action": "press_hotkey", "value": "win+r"},
                            level=3)
    assert d == Decision.DENY  # blocklist still applies
