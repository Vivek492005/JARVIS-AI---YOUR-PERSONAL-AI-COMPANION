"""Task 1.11: adversarial security suite — policy matrix, red-team edition.

Beyond the contract matrix in tests/test_policy.py: taint and rate-limit
at max autonomy, SYSTEM never auto-allowing, and arg-rules beating the tier.
"""

import sys
from unittest.mock import MagicMock

for _mod in ("speech_recognition", "pyttsx3"):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))


from access_os.policy import (  # noqa: E402
    Decision, PolicyContext, decide, decide_tool_call,
)
from access_os.tools.registry import Risk, ToolSpec  # noqa: E402
from access_os.tools.registry import WebSearchParams  # noqa: E402


def _spec(risk):
    return ToolSpec(name="t", description="t", params=WebSearchParams,
                    risk=risk, handler=lambda a, c, n: "")


def test_system_never_auto_even_l3_untainted():
    assert decide(_spec(Risk.SYSTEM), PolicyContext(), 3) == Decision.CONFIRM


def test_tainted_and_rate_limited_is_deny():
    ctx = PolicyContext(tainted=True, rate_limited=True)
    assert decide(_spec(Risk.READ), ctx, 3) == Decision.DENY


def test_rate_limited_beats_l3_destructive():
    ctx = PolicyContext(rate_limited=True)
    assert decide(_spec(Risk.DESTRUCTIVE), ctx, 3) == Decision.DENY


def test_arg_rules_beat_l3_tier():
    # PowerShell destructive: DENY even at max autonomy.
    d, _ = decide_tool_call("run_powershell_command",
                            {"command": "Remove-Item C:\\x"}, level=3)
    assert d == Decision.DENY
    # Blocked hotkey: DENY even at max autonomy.
    d, _ = decide_tool_call("keyboard_mouse_action",
                            {"action": "press_hotkey", "value": "alt+f4"},
                            level=3)
    assert d == Decision.DENY
    # Bad URL scheme: DENY even at max autonomy.
    d, _ = decide_tool_call("open_website",
                            {"url_or_name": "file:///etc/passwd"}, level=3)
    assert d == Decision.DENY


def test_invalid_level_fails_restrictive():
    # Out-of-range autonomy levels fall back to the most restrictive tier
    # (READ auto, everything else confirms) — never more permissive.
    for bad_level in (-1, 4, 99):
        d, _ = decide_tool_call("web_search", {"query": "x"}, level=bad_level)
        assert d == Decision.ALLOW, f"level {bad_level}: READ should auto"
        d, _ = decide_tool_call("open_application", {"app_name": "x"},
                                level=bad_level)
        assert d == Decision.CONFIRM, f"level {bad_level}: must confirm"


def test_empty_args_fail_closed():
    d, _ = decide_tool_call("web_search", {}, level=3)
    assert d == Decision.DENY  # schema: query is required
    d, _ = decide_tool_call("open_application", {"app_name": ""}, level=3)
    assert d == Decision.DENY
