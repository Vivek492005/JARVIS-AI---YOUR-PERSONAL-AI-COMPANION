"""Tests for Task 1.2: tool registry with risk tiers + arg validation."""

import sys
from unittest.mock import MagicMock

import pytest

# Stub heavy modules before importing actions (pyautogui needs a display).
for _mod in ("pyautogui",):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))

from access_os.tools.registry import (
    REGISTRY, Risk, ToolSpec, function_schemas, resolve, tool,
)
from access_os.actions import execute_tool_raw, manage_notes


def test_all_eight_tools_registered():
    base = sorted(n for n in REGISTRY if "." not in n)
    legacy = ["download_media", "keyboard_mouse_action", "manage_notes",
              "open_application", "open_website", "run_command",
              "run_powershell_command", "system_control", "web_search"]
    # Phase 5 adds perception tools; legacy set must stay registered.
    assert all(t in base for t in legacy)


def test_unregistered_tool_rejected():
    assert "not recognized" in execute_tool_raw("delete_everything", {})


def test_invalid_args_rejected_cleanly():
    r = execute_tool_raw("manage_notes", {"action": "nuke"})
    assert r.startswith("Invalid arguments for manage_notes")
    r = execute_tool_raw("download_media",
                         {"url_or_query": "x", "media_type": "exe"})
    assert r.startswith("Invalid arguments for download_media")
    r = execute_tool_raw("open_application", {"app_name": ""})
    assert r.startswith("Invalid arguments for open_application")


def test_risk_tiers():
    assert resolve("web_search", {"query": "x"}).risk == Risk.READ
    assert resolve("open_application", {"app_name": "x"}).risk == Risk.REVERSIBLE
    assert resolve("download_media", {"url_or_query": "x"}).risk == Risk.REVERSIBLE
    assert resolve("system_control",
                   {"action": "take_screenshot"}).risk == Risk.READ
    assert resolve("system_control",
                   {"action": "check_battery"}).risk == Risk.READ
    assert resolve("system_control",
                   {"action": "volume_up"}).risk == Risk.REVERSIBLE
    assert resolve("system_control",
                   {"action": "empty_recycle_bin"}).risk == Risk.DESTRUCTIVE
    assert resolve("system_control",
                   {"action": "lock_pc"}).risk == Risk.SYSTEM
    assert resolve("manage_notes", {"action": "save"}).risk == Risk.REVERSIBLE
    assert resolve("manage_notes", {"action": "clear"}).risk == Risk.DESTRUCTIVE
    assert resolve("keyboard_mouse_action",
                   {"action": "type_text"}).risk == Risk.REVERSIBLE
    assert resolve("keyboard_mouse_action",
                   {"action": "press_hotkey", "value": "ctrl+s"}).risk == Risk.REVERSIBLE
    assert resolve("keyboard_mouse_action",
                   {"action": "press_hotkey", "value": "ctrl+shift+x"}).risk == Risk.SYSTEM
    assert resolve("run_command",
                   {"command_key": "ipconfig"}).risk == Risk.READ
    assert resolve("run_powershell_command",
                   {"command": "Get-Date"}).risk == Risk.SYSTEM


def test_unknown_action_fails_closed_to_system():
    # An action with no sub-spec gets the base tool's (highest) risk.
    assert resolve("system_control", {"action": "format_c_drive"}).risk == Risk.SYSTEM


def test_function_schemas_auto_generated():
    schemas = function_schemas()
    assert len(schemas) >= 9  # run_command added in 1.4; Phase 5 adds more
    names = {s["function"]["name"] for s in schemas}
    assert "open_application" in names and "run_powershell_command" in names
    for s in schemas:
        params = s["function"]["parameters"]
        assert params["type"] == "object"
        assert "properties" in params
    # schema and executor agree on required fields
    app_schema = next(s for s in schemas
                      if s["function"]["name"] == "open_application")
    assert "app_name" in app_schema["function"]["parameters"]["required"]


def test_duplicate_registration_rejected():
    spec = ToolSpec(name="open_application", description="dup",
                    params=REGISTRY["open_application"].params,
                    risk=Risk.READ, handler=lambda a, c, n: "")
    with pytest.raises(ValueError):
        tool(spec)


def test_manage_notes_rejects_path_traversal():
    assert "Invalid notes file" in manage_notes("save", "x", "../evil.txt")
    assert "Invalid notes file" in manage_notes("save", "x", "/abs/path.txt")
    assert "Invalid notes file" in manage_notes("read", None, "a/b.txt")


def test_registry_params_have_no_notes_file():
    # A-06: dispatcher-provided args must not be LLM-controllable.
    for name, spec in REGISTRY.items():
        if "manage_notes" in name:
            assert "notes_file" not in spec.params.model_fields


class TestCalculator:
    """A-07: AST evaluator — arithmetic works, DoS/injection don't."""

    def _calc(self, expr):
        import re
        from unittest.mock import MagicMock as M
        sys.modules.setdefault("speech_recognition", M())
        sys.modules.setdefault("pyttsx3", M())
        sys.modules.setdefault("pyperclip", M())
        sys.modules.setdefault("fuzzywuzzy", M())
        from access_os.voice_interface import VoiceCommandProcessor
        proc = VoiceCommandProcessor.__new__(VoiceCommandProcessor)
        m = M()
        m.group = lambda i: expr
        return proc._action_calculate(m)

    def test_basic_arithmetic(self):
        assert self._calc("2 + 3 * 4") == "2 + 3 * 4 is 14"
        assert self._calc("(10 - 4) / 3") == "(10 - 4) / 3 is 2.0"
        assert self._calc("2^10") == "2^10 is 1024"

    def test_huge_exponent_rejected(self):
        assert "could not calculate" in self._calc("9^9^9^9")

    def test_injection_rejected(self):
        assert "could not calculate" in self._calc("__import__('os')")
        assert "could not calculate" in self._calc("2 + 3; 4")
