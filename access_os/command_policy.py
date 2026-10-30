"""
command_policy.py — Security gate for JARVIS tool execution.

Every tool call the LLM (or the legacy regex engine) wants to run MUST pass
through `check_tool_call()` BEFORE execution. The gate returns one of three
verdicts:

    "allow"   — safe, execute immediately.
    "confirm" — legitimate but destructive/irreversible; ask the user first.
    "deny"    — blocked, never execute. The denial reason is returned to the
                LLM so it can explain (or offer a safe alternative).

Design principles:
  * Default-deny for PowerShell: only an explicit allowlist of read-only
    cmdlets may run. Everything else is denied — no "looks safe" heuristics.
  * Blocklist is checked FIRST, so a blocked cmdlet can't sneak in through an
    allowlisted prefix (e.g. "Get-ChildItem; Remove-Item C:\\").
  * The validator is pure Python with zero dependencies and no network access,
    so it can be unit-tested without API keys and cannot be bypassed by
    prompt injection — it inspects the final command string, not the LLM's
    intentions.

Usage:
    from access_os.command_policy import check_tool_call

    verdict, reason = check_tool_call("run_powershell_command",
                                      {"command": "Get-ChildItem C:\\Users"})
    if verdict == "deny":
        return f"Blocked for safety: {reason}"
    if verdict == "confirm":
        return f"ACTION_REQUIRES_CONFIRMATION: {confirmation_prompt(...)}"
    # ... execute normally, then log to the audit trail
"""

import re
from typing import Dict, Any, Tuple

# Verdict constants
ALLOW = "allow"
CONFIRM = "confirm"
DENY = "deny"

Verdict = Tuple[str, str]  # (verdict, human-readable reason)


# ---------------------------------------------------------------------------
# PowerShell policy
# ---------------------------------------------------------------------------

# Read-only cmdlets that are useful for "look something up" queries.
# Anchored at the start (^) so "X; Get-ChildItem" can't piggyback.
_PS_ALLOWLIST = [
    r"^Get-ChildItem\b",
    r"^Get-Content\b",
    r"^Get-Process\b",
    r"^Get-Service\b",
    r"^Get-Date\b",
    r"^Get-Location\b",
    r"^Get-ComputerInfo\b",
    r"^Get-Command\b",
    r"^Get-Culture\b",
    r"^Get-UICulture\b",
    r"^Test-Path\b",
]

# Anything matching these is denied, even if an allowlist pattern also matches.
# Covers: destructive cmdlets, code execution, exfiltration/download,
# file writes (redirection), command chaining, and PowerShell escape hatches.
_PS_BLOCKLIST = [
    # destructive / state-changing
    r"\bRemove-Item\b", r"\bClear-RecycleBin\b", r"\bStop-Process\b",
    r"\bStart-Process\b", r"\bNew-Item\b", r"\bCopy-Item\b", r"\bMove-Item\b",
    r"\bRename-Item\b", r"\bClear-Content\b", r"\bSet-Content\b",
    r"\bAdd-Content\b", r"\bSet-ItemProperty\b", r"\bNew-ItemProperty\b",
    r"\bFormat-[A-Za-z]+\b", r"\bOut-File\b", r"\bRestart-Computer\b",
    r"\bStop-Computer\b",
    # code execution / policy bypass
    r"\bInvoke-Expression\b", r"\bInvoke-Command\b",
    r"\bSet-ExecutionPolicy\b", r"\bStart-Job\b",
    # exfiltration / download (notes, screenshots and file contents stay local)
    r"\bInvoke-WebRequest\b", r"\bInvoke-RestMethod\b",
    r"\bcurl(\.exe)?\b", r"\bwget(\.exe)?\b", r"\bNet\.WebClient\b",
    # chaining / redirection / escapes — checked as literals
    r";", r"\|", r"&", r">", r"<",
    r"\$\(", r"`",
]


def validate_powershell(command: str) -> Verdict:
    """Validate a PowerShell command string. Default-deny."""
    cmd = (command or "").strip()
    if not cmd:
        return (DENY, "empty command")

    for pattern in _PS_BLOCKLIST:
        if re.search(pattern, cmd, re.IGNORECASE):
            return (DENY, f"blocked pattern in command ({pattern.strip(chr(92) + 'b')})")

    for pattern in _PS_ALLOWLIST:
        if re.search(pattern, cmd, re.IGNORECASE):
            return (ALLOW, "allowlisted read-only command")

    return (DENY, "command is not in the read-only allowlist")


# ---------------------------------------------------------------------------
# Keyboard / hotkey policy
# ---------------------------------------------------------------------------

# Normalized as "alt+f4" (lowercase, no spaces). These combos can close apps,
# open run dialogs, or are part of known prompt-injection kill chains
# (e.g. win+r -> type -> enter).
_BLOCKED_HOTKEYS = frozenset({
    "alt+f4",
    "ctrl+alt+del",
    "ctrl+alt+delete",
    "win+r",
    "super+r",
})


def _normalize_hotkey(value: str) -> str:
    parts = [p.strip() for p in (value or "").lower().replace(" ", "").split("+")]
    return "+".join(p for p in parts if p)


def validate_hotkey(value: str) -> Verdict:
    """Validate a hotkey combination like 'ctrl+s'."""
    norm = _normalize_hotkey(value)
    if not norm:
        return (DENY, "empty hotkey")
    if norm in _BLOCKED_HOTKEYS:
        return (DENY, f"hotkey '{norm}' is blocked for safety")
    return (ALLOW, "hotkey permitted")


# ---------------------------------------------------------------------------
# Destructive-action classification
# ---------------------------------------------------------------------------

# system_control actions that are disruptive/irreversible -> need confirmation.
_CONFIRM_SYSTEM_ACTIONS = frozenset({"empty_recycle_bin", "lock_pc"})

_CONFIRM_DESCRIPTIONS = {
    "empty_recycle_bin": "permanently empty your Recycle Bin",
    "lock_pc": "lock your PC",
    "clear_notes": "permanently delete all your saved notes",
}


def confirmation_prompt(tool_name: str, args: Dict[str, Any]) -> str:
    """Human-readable description of what the user is being asked to confirm."""
    if tool_name == "system_control":
        action = args.get("action", "")
        what = _CONFIRM_DESCRIPTIONS.get(action, f"perform '{action}'")
        return f"This will {what}. Say 'yes' to confirm, anything else to cancel."
    if tool_name == "manage_notes" and args.get("action") == "clear":
        return f"This will {_CONFIRM_DESCRIPTIONS['clear_notes']}. Say 'yes' to confirm, anything else to cancel."
    return "This action is destructive. Say 'yes' to confirm, anything else to cancel."


# ---------------------------------------------------------------------------
# Main gate — call this before executing ANY tool
# ---------------------------------------------------------------------------

def check_tool_call(tool_name: str, args: Dict[str, Any]) -> Verdict:
    """
    Return (verdict, reason) for a proposed tool call.

    Tools with no specific policy are allowed — the dangerous ones
    (shell, hotkeys, destructive system actions) each have explicit rules.
    """
    args = args or {}

    if tool_name == "run_powershell_command":
        return validate_powershell(args.get("command", ""))

    if tool_name == "keyboard_mouse_action":
        if args.get("action") == "press_hotkey":
            return validate_hotkey(args.get("value", ""))
        # type_text / press_key of ordinary keys is permitted
        return (ALLOW, "typing/key-press permitted")

    if tool_name == "system_control":
        action = args.get("action", "")
        if action in _CONFIRM_SYSTEM_ACTIONS:
            return (CONFIRM, f"'{action}' is disruptive and needs user confirmation")
        return (ALLOW, "system action permitted")

    if tool_name == "manage_notes":
        if args.get("action") == "clear":
            return (CONFIRM, "clearing all notes is irreversible")
        return (ALLOW, "notes action permitted")

    # open_application, open_website, web_search, download_media: no policy yet.
    return (ALLOW, "no policy rule for this tool — permitted")
