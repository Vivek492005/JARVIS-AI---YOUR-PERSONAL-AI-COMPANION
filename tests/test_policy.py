"""Tests for Task 1.3: policy engine + autonomy dial.

The contract is the (level x risk x tainted) decision matrix.
"""

import pytest

from access_os.policy import (
    AUTO_UP_TO,
    CONFIRM_NO,
    CONFIRM_TIMEOUT_S,
    CONFIRM_YES,
    Decision,
    PolicyContext,
    confirmation_question,
    decide,
    decide_tool_call,
    describe_action,
)
from access_os.tools.registry import Risk, ToolSpec
from access_os.tools.registry import WebSearchParams


def _spec(risk):
    return ToolSpec(name="t", description="t", params=WebSearchParams,
                    risk=risk, handler=lambda a, c, n: "")


# ---------------------------------------------------------------------------
# The matrix: (level x risk x tainted) -> Decision
# ---------------------------------------------------------------------------

MATRIX = {
    # level: {risk: {tainted: decision}}
    0: {r: {False: Decision.CONFIRM, True: Decision.CONFIRM}
        for r in Risk},
    1: {
        Risk.READ:        {False: Decision.ALLOW,   True: Decision.ALLOW},
        Risk.REVERSIBLE:  {False: Decision.CONFIRM, True: Decision.CONFIRM},
        Risk.DESTRUCTIVE: {False: Decision.CONFIRM, True: Decision.CONFIRM},
        Risk.SYSTEM:      {False: Decision.CONFIRM, True: Decision.CONFIRM},
    },
    2: {
        Risk.READ:        {False: Decision.ALLOW,   True: Decision.ALLOW},
        Risk.REVERSIBLE:  {False: Decision.ALLOW,   True: Decision.CONFIRM},
        Risk.DESTRUCTIVE: {False: Decision.CONFIRM, True: Decision.CONFIRM},
        Risk.SYSTEM:      {False: Decision.CONFIRM, True: Decision.CONFIRM},
    },
    3: {
        Risk.READ:        {False: Decision.ALLOW,   True: Decision.ALLOW},
        Risk.REVERSIBLE:  {False: Decision.ALLOW,   True: Decision.CONFIRM},
        Risk.DESTRUCTIVE: {False: Decision.ALLOW,   True: Decision.CONFIRM},
        Risk.SYSTEM:      {False: Decision.CONFIRM, True: Decision.CONFIRM},
    },
}


@pytest.mark.parametrize("level", [0, 1, 2, 3])
@pytest.mark.parametrize("risk", list(Risk))
@pytest.mark.parametrize("tainted", [False, True])
def test_decision_matrix(level, risk, tainted):
    ctx = PolicyContext(tainted=tainted)
    assert decide(_spec(risk), ctx, level) == MATRIX[level][risk][tainted]


def test_rate_limited_is_deny():
    ctx = PolicyContext(rate_limited=True)
    assert decide(_spec(Risk.READ), ctx, 3) == Decision.DENY


def test_system_always_confirms_even_at_l3():
    assert decide(_spec(Risk.SYSTEM), PolicyContext(), 3) == Decision.CONFIRM


def test_auto_up_to_mapping():
    assert AUTO_UP_TO[1] == Risk.READ
    assert AUTO_UP_TO[2] == Risk.REVERSIBLE
    assert AUTO_UP_TO[3] == Risk.DESTRUCTIVE


# ---------------------------------------------------------------------------
# decide_tool_call: registry tier x arg rules, stricter wins
# ---------------------------------------------------------------------------

def test_unregistered_tool_is_deny():
    d, reason = decide_tool_call("delete_everything", {}, level=3)
    assert d == Decision.DENY
    assert "not recognized" in reason


def test_l1_read_auto_reversible_confirm():
    d, _ = decide_tool_call("web_search", {"query": "x"}, level=1)
    assert d == Decision.ALLOW
    d, reason = decide_tool_call("open_application", {"app_name": "x"}, level=1)
    assert d == Decision.CONFIRM
    assert "confirmation" in reason.lower()


def test_l2_reversible_auto():
    d, _ = decide_tool_call("open_application", {"app_name": "x"}, level=2)
    assert d == Decision.ALLOW
    d, _ = decide_tool_call("system_control", {"action": "empty_recycle_bin"},
                            level=2)
    assert d == Decision.CONFIRM


def test_arg_rules_still_apply_at_l3():
    # PowerShell destructive cmdlet: denied even at max autonomy.
    d, _ = decide_tool_call("run_powershell_command",
                            {"command": "Remove-Item C:\\x"}, level=3)
    assert d == Decision.DENY
    # Blocked hotkey: denied even at max autonomy.
    d, _ = decide_tool_call("keyboard_mouse_action",
                            {"action": "press_hotkey", "value": "alt+f4"},
                            level=3)
    assert d == Decision.DENY


def test_tainted_turn_confirms_non_read():
    ctx = PolicyContext(tainted=True)
    d, _ = decide_tool_call("open_application", {"app_name": "x"}, ctx, level=3)
    assert d == Decision.CONFIRM
    d, _ = decide_tool_call("web_search", {"query": "x"}, ctx, level=3)
    assert d == Decision.ALLOW


# ---------------------------------------------------------------------------
# Confirmation UX (1.3.3 / 1.3.5)
# ---------------------------------------------------------------------------

def test_confirm_vocabulary():
    for w in ("haan", "yes", "confirm", "kar do", "haan kar de"):
        assert w in CONFIRM_YES
    for w in ("nahi", "no", "ruko", "cancel", "stop"):
        assert w in CONFIRM_NO
    assert CONFIRM_TIMEOUT_S == 10.0  # unanswered -> DENY (fail closed)


def test_confirmation_question_is_exact():
    q = confirmation_question("system_control", {"action": "empty_recycle_bin"})
    assert "Recycle Bin" in q and "haan" in q
    q = confirmation_question("manage_notes",
                              {"action": "save", "content": "x" * 50})
    assert "50 chars" in q
    q = confirmation_question("open_website", {"url_or_name": "http://evil"},
                              tainted_args=True)
    assert "untrusted source" in q


def test_describe_action_exactness():
    assert "Recycle Bin" in describe_action(
        "system_control", {"action": "empty_recycle_bin"}, None)
    assert "Remove-Item" in describe_action(
        "run_powershell_command", {"command": "Remove-Item C:\\x"}, None)
