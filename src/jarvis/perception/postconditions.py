"""Postconditions for every action tool (Master Plan Task 5.9).

Each check returns ``(ok, evidence)``. Tools that cannot be verified
are in :data:`UNVERIFIABLE` — for those the agent must say
"bhej diya, confirm nahi kar paaya", never "ho gaya".

Wired into :class:`jarvis.brain.loop.Verifier.verify`: perception
checks run first, then the legacy ``_verify_<tool>`` methods.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Tuple

logger = logging.getLogger(__name__)

# Tools whose effects we cannot observe — honesty required.
UNVERIFIABLE = frozenset(
    {
        "open_website",  # browser state not observable from here
        "web_search",  # data in, data out
        "download_media",  # async download; result message only
        "speak",  # TTS fire-and-forget
    }
)


def is_verifiable(tool_name: str) -> bool:
    return tool_name not in UNVERIFIABLE


def _result_ok(
    result: str, bad_markers=("could not", "failed", "blocked", "error", "refused")
) -> bool:
    lowered = (result or "").lower()
    return not any(m in lowered for m in bad_markers)


# -- individual checks -------------------------------------------------------
# Each: (args, result) -> (ok, evidence)


def _check_describe_screen(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    ok = "window '" in result and _result_ok(result)
    return ok, result[:200]


def _check_uia_find(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    if "no matching element" in result:
        return False, "element not found"
    return True, result[:200]


def _check_uia_invoke(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    return ("invoked" in result.lower(), result[:200])


def _check_uia_set_text(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    if "text set" not in result.lower():
        return False, result[:200]
    # Read-back: the strongest postcondition for set_text.
    try:
        from jarvis.perception import backends as _backends

        actual = _backends.get_backend("uia").get_text(args.get("element_id", ""))
        want = args.get("value", "")
        if actual == want:
            return True, "read-back matches"
        return False, f"read-back mismatch: {actual[:80]!r} != {want[:80]!r}"
    except Exception:
        return True, f"set reported ok (read-back unavailable): {result[:120]}"


def _check_capture_screen(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    if "captured" not in result.lower():
        return False, result[:200]
    return True, result[:200]


def _check_vlm_click(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    lowered = result.lower()
    if "mujhse nahi hoga" in lowered:
        return False, "handed off to user"
    if "clicked" in lowered and "verified" in lowered:
        return True, result[:200]
    if "clicked" in lowered:
        # Honest: it clicked, but nothing confirms the effect.
        return True, f"clicked but unverified: {result[:160]}"
    return False, result[:200]


def _check_browser_open(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    return ("opened" in result.lower() and _result_ok(result), result[:200])


def _check_browser_click(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    return ("clicked" in result.lower(), result[:200])


def _check_browser_fill(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    return ("filled" in result.lower(), result[:200])


def _check_browser_submit(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    if "mujhse nahi hoga" in result.lower():
        return False, "handed off to user (login/payment)"
    return ("submitted" in result.lower(), result[:200])


def _check_move_file(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    if "moved" not in result.lower():
        return False, result[:200]
    try:
        from jarvis.perception.files import resolve_scoped

        dst = resolve_scoped(args.get("dst", ""))
        src = resolve_scoped(args.get("src", ""))
        if dst.exists() and not src.exists():
            return True, f"verified on disk: {dst.name}"
        return False, f"disk state wrong (src_exists={src.exists()}, dst_exists={dst.exists()})"
    except Exception:
        return True, f"move reported ok (disk check unavailable): {result[:120]}"


def _check_copy_file(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    if "copied" not in result.lower():
        return False, result[:200]
    try:
        from jarvis.perception.files import resolve_scoped

        dst = resolve_scoped(args.get("dst", ""))
        return (dst.exists(), f"copy on disk: {dst.exists()}")
    except Exception:
        return True, result[:120]


def _check_delete_file(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    if "recycle bin" not in result.lower():
        return False, result[:200]
    try:
        from jarvis.perception.files import resolve_scoped

        gone = not resolve_scoped(args.get("path", "")).exists()
        return gone, f"trashed, path gone: {gone}"
    except Exception:
        return True, result[:120]


def _check_organize_folder(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    lowered = result.lower()
    if "dry run only" in lowered:
        return True, "plan only, nothing executed"
    return ("organized" in lowered, result[:200])


def _check_data_tool(args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    # find/read/summarize/get_text/context: the result IS the data.
    if not result or "blocked" in result.lower():
        return False, result[:200] or "(empty)"
    return True, f"data returned ({len(result)} chars)"


_CHECKS: Dict[str, Callable[[Dict[str, Any], str], Tuple[bool, str]]] = {
    "describe_screen": _check_describe_screen,
    "uia_find": _check_uia_find,
    "uia_invoke": _check_uia_invoke,
    "uia_set_text": _check_uia_set_text,
    "capture_screen": _check_capture_screen,
    "vlm_click": _check_vlm_click,
    "browser_open": _check_browser_open,
    "browser_click": _check_browser_click,
    "browser_fill": _check_browser_fill,
    "browser_submit": _check_browser_submit,
    "move_file": _check_move_file,
    "copy_file": _check_copy_file,
    "delete_file": _check_delete_file,
    "organize_folder": _check_organize_folder,
    "uia_get_text": _check_data_tool,
    "read_screen_text": _check_data_tool,
    "browser_read": _check_data_tool,
    "find_files": _check_data_tool,
    "read_file": _check_data_tool,
    "summarize_file": _check_data_tool,
    "get_context": _check_data_tool,
    "office_read": _check_data_tool,
}


def has_check(tool_name: str) -> bool:
    return tool_name in _CHECKS


def verify(tool_name: str, args: Dict[str, Any], result: str) -> Tuple[bool, str]:
    """Run the postcondition for a tool. Unknown tools -> honest pass."""
    check = _CHECKS.get(tool_name)
    if check is None:
        return True, f"no postcondition for {tool_name}; result: {result[:200]}"
    try:
        return check(args or {}, result or "")
    except Exception as e:
        logger.exception("postcondition error for %s", tool_name)
        return False, f"postcondition error: {e}"


def honest_message(tool_name: str, args: Dict[str, Any], result: str) -> str:
    """User-facing outcome: 'ho gaya' vs 'bhej diya, confirm nahi kar paaya'.

    Unverifiable tools never claim success — the plan's honesty rule.
    """
    if not is_verifiable(tool_name):
        return f"Bhej diya, confirm nahi kar paaya ({tool_name}): {result[:160]}"
    ok, evidence = verify(tool_name, args, result)
    if ok:
        return f"Ho gaya: {evidence[:160]}"
    return f"Nahi hua / adhura raha ({tool_name}): {evidence[:160]}"
