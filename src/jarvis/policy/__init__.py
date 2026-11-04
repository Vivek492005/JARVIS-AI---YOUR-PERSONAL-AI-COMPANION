"""Policy engine + autonomy dial (Master Plan Task 1.3).

One place decides allow/confirm/deny for every tool call. The decision
combines:
  1. the tool's risk tier vs the autonomy level (the matrix below), and
  2. the argument-level rules in access_os/command_policy.py
     (PowerShell allowlist, hotkey blocklist, …).

The STRICTER of the two always wins.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from ..tools.registry import Risk, ToolSpec, resolve


class Decision(Enum):
    ALLOW = 1
    CONFIRM = 2
    DENY = 3


# Autonomy dial: which risk tiers run without asking.
#   L0: ask for everything · L1 (default): READ auto · L2: READ+REVERSIBLE auto
#   L3: DESTRUCTIVE auto too — SYSTEM always confirms, no exceptions.
AUTO_UP_TO = {
    0: Risk.READ - 1,  # nothing is auto (READ=0 > -1)
    1: Risk.READ,
    2: Risk.REVERSIBLE,
    3: Risk.DESTRUCTIVE,
}


@dataclass
class PolicyContext:
    """Everything about the current turn that affects the decision."""

    tainted: bool = False  # untrusted content in context (Task 1.5)
    rate_limited: bool = False  # set by the Task 1.8 rate limiter
    provenance: Dict[str, str] = field(default_factory=dict)  # arg -> source
    remote: bool = False  # came from Telegram remote (Task 6.5)
    remote_system_tools: bool = False  # explicit opt-in for SYSTEM remotely
    safe_mode: bool = False  # Task 8.3: `jarvis --safe` — READ only
    offline: bool = False  # Task 8.3: deny tools with "network" scope


def context_from_settings() -> "PolicyContext":
    """Build a PolicyContext from the effective Settings (safe/offline modes).

    Never raises: falls back to a default context if settings can't load.
    """
    try:
        from jarvis.core.config import get_settings

        s = get_settings()
        return PolicyContext(safe_mode=s.safety.safe_mode, offline=s.privacy.offline)
    except Exception:
        return PolicyContext()


# --- Confirmation vocabulary (Task 1.3.3) -----------------------------------
# A confirmation is only valid as the user's *own* next turn / GUI click —
# never from ambient audio (see THREAT_MODEL.md).

CONFIRM_YES = frozenset(
    {
        "haan",
        "ha",
        "han",
        "yes",
        "yeah",
        "yep",
        "confirm",
        "confirmed",
        "haan kar de",
        "kar do",
        "kar de",
        "ok",
        "okay",
        "do it",
        "go ahead",
        "sure",
        "thik hai",
        "theek hai",
    }
)
CONFIRM_NO = frozenset(
    {
        "nahi",
        "nahin",
        "na",
        "no",
        "nope",
        "ruko",
        "ruk",
        "cancel",
        "stop",
        "mat karo",
        "rehn do",
        "rehen do",
    }
)

#: Unanswered confirmations fail closed after this many seconds.
CONFIRM_TIMEOUT_S = 10.0


def decide(spec: ToolSpec, ctx: PolicyContext, level: int) -> Decision:
    """The autonomy matrix. Pure function — fully table-testable."""
    # Task 8.3: safe mode — only READ tools run; everything above READ is
    # denied outright (not even confirmed). Reflex matching is outside the
    # policy gate, so reflexes keep working in safe mode.
    if ctx.safe_mode and spec.risk > Risk.READ:
        return Decision.DENY
    # Task 8.3: offline mode — tools that need the network are denied.
    if ctx.offline and "network" in spec.scopes:
        return Decision.DENY
    if spec.risk == Risk.SYSTEM:
        # Task 6.5: SYSTEM tools are disabled on the remote channel by
        # default (fail-closed); explicit opt-in restores CONFIRM.
        if ctx.remote and not ctx.remote_system_tools:
            return Decision.DENY
        return Decision.CONFIRM  # always
    if ctx.tainted and spec.risk > Risk.READ:
        return Decision.CONFIRM  # Task 1.5
    if ctx.rate_limited:
        return Decision.DENY
    auto_up_to = AUTO_UP_TO.get(level, Risk.READ)
    return Decision.ALLOW if spec.risk <= auto_up_to else Decision.CONFIRM


def _stricter(a: Decision, b: Decision) -> Decision:
    return a if a.value >= b.value else b


_CP_TO_DECISION = {"allow": Decision.ALLOW, "confirm": Decision.CONFIRM, "deny": Decision.DENY}


def describe_action(tool_name: str, args: Dict[str, Any], spec: Optional[ToolSpec]) -> str:
    """Exact action + arguments for the confirmation prompt (Task 1.3.5).

    Never a vague 'delete files' — always what + where + how many.
    """
    args = args or {}
    if tool_name == "system_control":
        action = args.get("action", "?")
        detail = {
            "empty_recycle_bin": "permanently empty the Recycle Bin",
            "lock_pc": "lock the workstation",
        }.get(action, action)
        return f"system action: {detail}"
    if tool_name == "manage_notes":
        return f"notes: {args.get('action', '?')}" + (
            f" ({len(args.get('content') or '')} chars)" if args.get("action") == "save" else ""
        )
    if tool_name == "run_powershell_command":
        return f"run PowerShell: {args.get('command', '?')}"
    if tool_name == "keyboard_mouse_action":
        return f"{args.get('action', '?')}: {str(args.get('value', ''))[:80]}"
    if tool_name == "download_media":
        media = str(args.get("url_or_query", ""))[:80]
        return f"download {args.get('media_type', 'audio')}: {media}"
    if tool_name == "open_application":
        return f"open application: {args.get('app_name', '?')}"
    if tool_name == "open_website":
        return f"open website: {args.get('url_or_query', args.get('url_or_name', '?'))}"
    return f"{tool_name} {str(args)[:120]}"


def decide_tool_call(
    tool_name: str,
    args: Optional[Dict[str, Any]],
    ctx: Optional[PolicyContext] = None,
    level: int = 1,
) -> Tuple[Decision, str]:
    """Full decision for one tool call: registry tier × arg rules.

    Returns (Decision, reason). Unknown tools are DENY (fail-closed).
    """
    from .command_policy import check_tool_call

    args = args or {}
    ctx = ctx or PolicyContext()
    spec = resolve(tool_name, args)
    if spec is None:
        return Decision.DENY, f"Tool {tool_name} is not recognized."

    # Schema validation at the gate: malformed args never reach the executor.
    try:
        spec.params(**args)
    except Exception as e:
        return Decision.DENY, f"invalid arguments: {e}"

    tier_decision = decide(spec, ctx, level)

    cp_verdict, cp_reason = check_tool_call(tool_name, args)
    arg_decision = _CP_TO_DECISION[cp_verdict]

    final = _stricter(tier_decision, arg_decision)
    if final == Decision.DENY:
        reason = (
            cp_reason
            if arg_decision == Decision.DENY
            else f"{describe_action(tool_name, args, spec)} is not allowed."
        )
    elif final == Decision.CONFIRM:
        if arg_decision == Decision.CONFIRM:
            reason = cp_reason  # e.g. "destructive action needs confirmation"
        else:
            reason = (
                f"{describe_action(tool_name, args, spec)} needs "
                f"confirmation (risk {spec.risk.name}, autonomy L{level})."
            )
    else:
        reason = "allowed"
    return final, reason


def confirmation_question(
    tool_name: str,
    args: Optional[Dict[str, Any]],
    spec: Optional[ToolSpec] = None,
    tainted_args: bool = False,
) -> str:
    """The spoken/GUI confirmation prompt: exact action + args."""
    q = f"{describe_action(tool_name, args or {}, spec)} — kar doon? (haan / nahi)"
    if tainted_args:
        q += " [ye value untrusted source se aayi hai]"
    return q
