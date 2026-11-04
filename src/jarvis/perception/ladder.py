"""Control-surface ladder (Master Plan Task 5.1).

Rule: always use the highest available rung.

| Rung | Surface                        | Reliability |
|------|--------------------------------|-------------|
| 1    | API / MCP                      | ★★★★★       |
| 2    | CLI / COM / PowerShell (allowlisted) | ★★★★☆  |
| 3    | UI Automation (accessibility tree)   | ★★★★☆  |
| 4    | DOM (Playwright)               | ★★★★☆       |
| 5    | OCR + coordinates              | ★★☆☆☆       |
| 6    | VLM pixel click                | ★☆☆☆☆       |

:func:`run_ladder` tries attempts from the highest rung down. Every
fallback is audit-logged ("UIA se fail, OCR par gaya") per the plan.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)


class Rung(IntEnum):
    API_MCP = 1
    CLI_COM = 2
    UIA = 3
    DOM = 4
    OCR = 5
    VLM = 6


RUNG_LABELS = {
    Rung.API_MCP: "API/MCP",
    Rung.CLI_COM: "CLI/COM/PowerShell",
    Rung.UIA: "UI Automation",
    Rung.DOM: "DOM (browser)",
    Rung.OCR: "OCR + coordinates",
    Rung.VLM: "VLM pixel click",
}


class AttemptFailed(Exception):
    """An attempt at one rung failed; the ladder should try the next."""


class LadderExhausted(Exception):
    """Every rung failed. Carries the per-rung failure reasons."""

    def __init__(self, task: str, failures: List[Tuple[Rung, str]]) -> None:
        self.task = task
        self.failures = failures
        detail = "; ".join(f"{RUNG_LABELS[r]}: {why}" for r, why in failures)
        super().__init__(f"ladder exhausted for {task!r}: {detail}")


@dataclass
class Attempt:
    """One rung's way of doing the task."""

    rung: Rung
    label: str
    fn: Callable[[], str]
    available: bool = True  # False = backend missing; skip without audit noise


def _audit_fallback(task: str, failed_rung: Rung, why: str, next_rung: Optional[Rung]) -> None:
    """Audit-log a ladder fallback (plan: 'UIA se fail, OCR par gaya')."""
    try:
        from jarvis.policy.audit import AuditLogger

        nxt = RUNG_LABELS[next_rung] if next_rung else "handoff"
        AuditLogger().log(
            "ladder.fallback",
            {"task": task, "from": RUNG_LABELS[failed_rung], "to": nxt},
            decision="fallback",
            reason=f"{RUNG_LABELS[failed_rung]} failed ({why}); trying {nxt}",
        )
    except Exception:
        logger.exception("ladder audit failed")


def run_ladder(task: str, attempts: List[Attempt], audit: bool = True) -> Tuple[Rung, str]:
    """Try attempts highest-rung-first; return (winning_rung, result).

    Attempts must be pre-sorted highest-first (Rung 1 = best). Unavailable
    rungs are skipped silently; failed rungs are audit-logged as fallbacks.
    Raises :class:`LadderExhausted` when nothing works.
    """
    ordered = sorted(attempts, key=lambda a: (a.rung.value, a.label))
    failures: List[Tuple[Rung, str]] = []
    for i, attempt in enumerate(ordered):
        if not attempt.available:
            continue
        try:
            result = attempt.fn()
        except AttemptFailed as e:
            why = str(e) or "no reason given"
            failures.append((attempt.rung, why))
            remaining = [a for a in ordered[i + 1 :] if a.available]
            nxt = remaining[0].rung if remaining else None
            if audit:
                _audit_fallback(task, attempt.rung, why, nxt)
            continue
        except Exception as e:  # unexpected error: also fall through
            why = f"unexpected: {type(e).__name__}: {e}"
            failures.append((attempt.rung, why))
            remaining = [a for a in ordered[i + 1 :] if a.available]
            nxt = remaining[0].rung if remaining else None
            if audit:
                _audit_fallback(task, attempt.rung, why, nxt)
            continue
        return attempt.rung, result
    raise LadderExhausted(task, failures)


def rung_for_tool(tool_name: str) -> Rung:
    """Best rung for a known tool (used to label audit entries)."""
    mapping = {
        "open_website": Rung.API_MCP,
        "web_search": Rung.API_MCP,
        "run_powershell_command": Rung.CLI_COM,
        "run_command": Rung.CLI_COM,
        "describe_screen": Rung.UIA,
        "uia_invoke": Rung.UIA,
        "uia_set_text": Rung.UIA,
        "browser_click": Rung.DOM,
        "browser_fill": Rung.DOM,
        "read_screen_text": Rung.OCR,
        "vlm_click": Rung.VLM,
    }
    return mapping.get(tool_name, Rung.UIA)
