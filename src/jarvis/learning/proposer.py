"""Proposal generation (Phase 9 moonshot): patterns -> proposals.

The proposer is OFFLINE and READ-ONLY: it scans the learning store and
emits concrete, reviewable proposals. It never applies anything.

Proposal types:
* ``reflex_rule`` — the same tool ran with identical args N+ times. A fast
  path may be worth it. The regex ``patterns`` are DELIBERATELY left empty:
  we never stored the raw utterance (privacy), so the human reviewer fills
  the pattern in. The proposal carries everything else (tool, args, reply
  draft, evidence).
* ``prompt_snippet`` — a tool keeps getting corrected/undone. A usage note
  in the prompt may prevent the mistake. Draft snippet included; the
  reviewer edits before approving.
* ``skill_variant`` — tools A->B fire in sequence repeatedly. A composite
  skill scaffold may be worth creating. The scaffold is inert (comment-only
  tool.py) until a developer fills it in.

Dedup: no second pending/approved proposal for the same (type, target).
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List

from jarvis.learning.store import LearningStore

logger = logging.getLogger(__name__)

DEFAULT_MIN_EVIDENCE = 3


def _confidence(n: int, threshold: int) -> float:
    # Frequency-based: at threshold -> 0.5, saturates at 0.95.
    return round(min(0.5 + 0.45 * (n - threshold) / max(threshold, 1), 0.95), 2)


def _rule_id(tool: str, args_hash: str) -> str:
    safe = "".join(c if (c.isalnum() or c == "_") else "_" for c in tool)
    return f"learned_{safe}_{args_hash[:8]}"


def propose_reflex_rules(store: LearningStore,
                         min_evidence: int = DEFAULT_MIN_EVIDENCE
                         ) -> List[str]:
    """Clusters of repeated identical tool calls -> reflex_rule proposals."""
    made = []
    for cl in store.run_clusters(min_count=min_evidence):
        tool, h = cl["tool"], cl["args_hash"]
        if not tool or not h:
            continue
        target = f"{tool}:{h}"
        if store.proposal_exists_for("reflex_rule", target):
            continue
        try:
            args = json.loads(cl["args_redacted"] or "{}")
        except ValueError:
            args = {}
        rule = {
            "id": _rule_id(tool, h),
            "patterns": [],  # reviewer fills in (privacy: utterance never stored)
            "tool": tool,
            "args": args if isinstance(args, dict) else {},
            "reply": "",
            "compute": None,
        }
        pid = store.add_proposal(
            ptype="reflex_rule", target=target,
            title=f"Reflex rule candidate: '{tool}' x{cl['n']}",
            body={"rule": rule},
            evidence={"runs": cl["n"], "allowed": cl["n_allow"],
                      "args_hash": h,
                      "note": "Same tool+args executed repeatedly. "
                              "Add regex patterns (from real utterances you "
                              "observed) before approving."},
            confidence=_confidence(cl["n"], min_evidence))
        made.append(pid)
    return made


_CORRECTION_SNIPPETS = {
    "undo": ("The user undid this tool's action more than once. Double-check "
             "arguments with the user before acting, and prefer the least "
             "surprising interpretation."),
    "confirm_decline": ("The user declined the confirmation prompt repeatedly. "
                        "Summarize exactly what will happen (including "
                        "side effects) BEFORE asking, in one short line."),
    "user_correction": ("The user corrected this tool's usage. If the request "
                        "is ambiguous, ask a clarifying question instead of "
                        "guessing."),
}


def propose_prompt_snippets(store: LearningStore,
                            min_evidence: int = 2) -> List[str]:
    """Repeated corrections on a tool -> prompt_snippet proposals."""
    made = []
    for cl in store.correction_clusters(min_count=min_evidence):
        tool, kind = cl["tool"], cl["kind"]
        if not tool:
            continue
        target = f"{tool}:{kind}"
        if store.proposal_exists_for("prompt_snippet", target):
            continue
        draft = _CORRECTION_SNIPPETS.get(
            kind, "The user corrected this tool's usage; be extra careful.")
        title = f"Usage note for '{tool}' ({kind} x{cl['n']})"
        pid = store.add_proposal(
            ptype="prompt_snippet", target=target, title=title,
            body={"section_title": f"Learned: {tool}",
                  "markdown": f"**{tool}**: {draft}"},
            evidence={"corrections": cl["n"], "kind": kind},
            confidence=_confidence(cl["n"], min_evidence))
        made.append(pid)
    return made


def propose_skill_variants(store: LearningStore,
                           min_evidence: int = DEFAULT_MIN_EVIDENCE
                           ) -> List[str]:
    """Frequent A->B tool sequences -> skill_variant proposals."""
    made = []
    for seq in store.tool_sequences(min_count=min_evidence):
        a, b = [s.strip() for s in seq["sequence"].split("->")]
        name = f"learned-{(a + '-' + b).replace('_', '-')[:40]}"
        if store.proposal_exists_for("skill_variant", name):
            continue
        pid = store.add_proposal(
            ptype="skill_variant", target=name,
            title=f"Composite skill candidate: {a} -> {b} (x{seq['n']})",
            body={"skill_name": name,
                  "description":
                      f"Learned composite: runs '{a}' then '{b}'. "
                      f"Observed {seq['n']} times. Scaffold only — a "
                      f"developer must implement tool.py.",
                  "suggested_tools": [a, b]},
            evidence={"sequence": seq["sequence"], "occurrences": seq["n"]},
            confidence=_confidence(seq["n"], min_evidence))
        made.append(pid)
    return made


def generate_proposals(store: LearningStore,
                       min_evidence: int = DEFAULT_MIN_EVIDENCE
                       ) -> Dict[str, List[str]]:
    """Run all proposers. Returns {type: [proposal_ids]}."""
    out = {
        "reflex_rule": propose_reflex_rules(store, min_evidence),
        "prompt_snippet": propose_prompt_snippets(store, min_evidence),
        "skill_variant": propose_skill_variants(store, min_evidence),
    }
    total = sum(len(v) for v in out.values())
    logger.info("proposer: %d new proposal(s)", total)
    return out
