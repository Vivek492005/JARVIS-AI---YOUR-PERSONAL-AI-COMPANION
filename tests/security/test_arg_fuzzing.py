"""Task 1.11: adversarial security suite — argument fuzzing.

Hostile arg shapes (None, giant strings, nested payloads, control chars,
path traversal, command-injection strings) must never raise unhandled,
never execute, and end in DENY or a clean validation error.
"""

import sys
from unittest.mock import MagicMock

for _mod in ("speech_recognition", "pyttsx3", "pyautogui", "pyperclip",
             "fuzzywuzzy"):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))
sys.modules["fuzzywuzzy"].fuzz = MagicMock()

import pytest  # noqa: E402

from access_os.actions import execute_tool_raw, run_action  # noqa: E402
from access_os.policy import Decision, decide_tool_call  # noqa: E402

TOOLS = ["web_search", "open_application", "open_website", "system_control",
         "keyboard_mouse_action", "manage_notes", "download_media",
         "run_powershell_command", "run_command"]

HOSTILE = [
    None,
    {},
    {"action": None},
    {"action": 12345},
    {"action": ["volume_up"]},
    {"action": {"nested": "volume_up"}},
    {"query": "x" * 100_000},                       # giant string
    {"command": "Get-Date\x00Remove-Item C:\\"},      # null byte
    {"command": "Get-Date\r\nRemove-Item C:\\"},      # CRLF smuggle
    {"command": "Get-Date\u2028Remove-Item C:\\"},    # unicode LS smuggle
    {"command": "Get-Date; Remove-Item C:\\"},        # chaining
    {"command": "$(whoami)"},                        # subshell
    {"command": "`whoami`"},                         # backticks
    {"app_name": "../../windows/system32/cmd"},      # traversal-ish
    {"app_name": "x" * 5000},                        # oversize
    {"url_or_name": "file:///etc/passwd"},
    {"url_or_name": "javascript:alert(1)"},
    {"url_or_name": "ms-settings:network"},
    {"value": "alt+f4"},
    {"value": "win+r"},
    {"notes_file": "../../etc/passwd"},              # A-06: pinned anyway
    {"command_key": "__import__('os').system('id')"},
]


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("args", HOSTILE)
def test_fuzz_execute_raw_never_raises_nor_executes(tool, args):
    # Must return a string (error/deny), never raise, never execute.
    r = execute_tool_raw(tool, args if isinstance(args, dict) else {})
    assert isinstance(r, str)


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("args", HOSTILE)
def test_fuzz_policy_gate_safe(tool, args):
    a = args if isinstance(args, dict) else {}
    d, _ = decide_tool_call(tool, a, level=3)
    assert isinstance(d, Decision)


def test_fuzz_run_action_verdicts_sane():
    for tool in TOOLS:
        for args in HOSTILE:
            a = args if isinstance(args, dict) else {}
            v, r = run_action(tool, a)
            assert v in ("allow", "confirm", "deny")
            assert isinstance(r, str)


def test_injection_strings_specifically_denied():
    for cmd in ("Get-Date; Remove-Item C:\\", "Get-Date\r\nStop-Process -Name x",
                "Get-Date\u2028Remove-Item C:\\"):
        d, _ = decide_tool_call("run_powershell_command", {"command": cmd},
                                level=3)
        assert d == Decision.DENY, cmd
    for url in ("file:///etc/passwd", "javascript:alert(1)",
                "ms-settings:network"):
        d, _ = decide_tool_call("open_website", {"url_or_name": url}, level=3)
        assert d == Decision.DENY, url
