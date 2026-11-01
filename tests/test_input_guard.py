"""Tests for Task 1.4: shell/typing escape path.

Foreground-window guard, hotkey tiers, allowlisted run_command.
"""

import sys
from unittest.mock import MagicMock

for _mod in ("pyautogui", "pyperclip"):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))

import pytest  # noqa: E402

from access_os import actions as A  # noqa: E402
from access_os.policy import decide_tool_call, Decision  # noqa: E402
from access_os.tools.registry import (  # noqa: E402
    REGISTRY, Risk, resolve, function_schemas,
)


# ---------------------------------------------------------------------------
# 1.4.1 foreground-window guard
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("proc", ["powershell.exe", "cmd.exe", "wt.exe",
                                  "conhost.exe", "regedit.exe", "taskmgr.exe"])
def test_typing_blocked_into_terminals(monkeypatch, proc):
    monkeypatch.setattr(A, "get_foreground_process", lambda: proc)
    r = A.keyboard_mouse_action("type_text", "hello")
    assert r.startswith("Blocked for safety")
    assert proc in r


def test_hotkey_blocked_into_terminals(monkeypatch):
    monkeypatch.setattr(A, "get_foreground_process", lambda: "powershell.exe")
    r = A.keyboard_mouse_action("press_hotkey", "ctrl+s")
    assert r.startswith("Blocked for safety")


def test_guard_passes_on_non_terminal(monkeypatch):
    monkeypatch.setattr(A, "get_foreground_process", lambda: "notepad.exe")
    r = A.keyboard_mouse_action("type_text", "hello")
    assert "Blocked" not in r


def test_guard_passes_when_unknown(monkeypatch):
    # Can't determine foreground (Linux / Win32 failed) -> open, but the
    # policy tier still governs.
    monkeypatch.setattr(A, "get_foreground_process", lambda: None)
    r = A.keyboard_mouse_action("type_text", "hello")
    assert "Blocked" not in r


# ---------------------------------------------------------------------------
# 1.4.2 hotkey tiers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hk", ["ctrl+c", "ctrl+v", "ctrl+x", "ctrl+z",
                                "ctrl+s", "ctrl+f", "ctrl+a", "ctrl+t",
                                "ctrl+w", "ctrl+r", "win+d", "CTRL + S"])
def test_safe_hotkeys_reversible(hk):
    spec = resolve("keyboard_mouse_action",
                   {"action": "press_hotkey", "value": hk})
    assert spec.risk == Risk.REVERSIBLE


def test_other_hotkeys_stay_system():
    spec = resolve("keyboard_mouse_action",
                   {"action": "press_hotkey", "value": "ctrl+shift+x"})
    assert spec.risk == Risk.SYSTEM


def test_blocked_hotkeys_denied_even_at_l3():
    d, _ = decide_tool_call("keyboard_mouse_action",
                            {"action": "press_hotkey", "value": "win+r"},
                            level=3)
    assert d == Decision.DENY


def test_safe_hotkey_auto_at_l2():
    d, _ = decide_tool_call("keyboard_mouse_action",
                            {"action": "press_hotkey", "value": "ctrl+s"},
                            level=2)
    assert d == Decision.ALLOW


# ---------------------------------------------------------------------------
# 1.4.3 allowlisted run_command
# ---------------------------------------------------------------------------

def test_run_command_registered_read():
    spec = REGISTRY["run_command"]
    assert spec.risk == Risk.READ
    names = {s["function"]["name"] for s in function_schemas()}
    assert "run_command" in names


def test_run_command_unknown_key_fail_closed():
    r = A.run_command("del *")
    assert "Unknown command" in r


def test_run_command_gate_rejects_invalid_key():
    d, reason = decide_tool_call("run_command", {"command_key": "del *"},
                                 level=3)
    assert d == Decision.DENY
    assert "invalid arguments" in reason


def test_run_command_executes_template(monkeypatch):
    calls = {}

    def fake_run(argv, **kwargs):
        calls["argv"] = argv
        assert kwargs.get("shell") is False
        m = MagicMock()
        m.stdout = "ok"
        return m

    monkeypatch.setattr(A.subprocess, "run", fake_run)
    r = A.run_command("ipconfig")
    assert calls["argv"] == ["ipconfig"]
    assert r == "ok"


def test_run_command_l1_auto():
    d, _ = decide_tool_call("run_command", {"command_key": "disk_free"},
                            level=1)
    assert d == Decision.ALLOW


# ---------------------------------------------------------------------------
# 1.4.4 lint: no shell execution paths in first-party source
# ---------------------------------------------------------------------------

def test_no_shell_true_or_os_system_in_source():
    import pathlib
    bad = []
    for p in list(pathlib.Path("access_os").rglob("*.py")) + \
            [pathlib.Path("main.py")]:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(),
                                 start=1):
            s = line.strip()
            if s.startswith("#"):
                continue
            if "shell=True" in line or "os.system(" in line:
                bad.append(f"{p}:{i}: {s[:70]}")
    assert not bad, f"shell execution paths found: {bad}"
