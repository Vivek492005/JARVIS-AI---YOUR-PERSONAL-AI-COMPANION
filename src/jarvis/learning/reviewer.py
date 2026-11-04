"""Human review of learning proposals (Phase 9 moonshot).

The reviewer is the ONLY path from proposal to production change:

* ``approve`` — validates the payload, runs the eval gate (fail-closed),
  applies the change to an allowlisted path with a versioned backup,
  audit-logs the decision. Any failure leaves the proposal ``pending``.
* ``reject`` / ``edit`` — reviewer decisions, audit-logged.
* ``revert`` — restores the backup of an applied change.

Safety invariants:
* Learned reflex rules may only target READ/REVERSIBLE tools — never
  DESTRUCTIVE/SYSTEM (a learned regex must never bypass confirmation).
* Applies write ONLY to allowlisted paths (learned-rules JSON, learned
  prompt file, new skill dirs). No arbitrary file writes.
* No auto-apply anywhere: approval is an explicit human action, behind
  the control center's bearer-token auth.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.learning.eval_gate import EvalGateResult, run_eval_gate
from jarvis.learning.store import LearningStore, _utcnow

logger = logging.getLogger(__name__)

# src/jarvis/learning/reviewer.py -> src/jarvis
_JARVIS_SRC = Path(__file__).resolve().parent.parent
_LEARNED_RULES = _JARVIS_SRC / "brain" / "reflex_learned.json"
_LEARNED_PROMPT = _JARVIS_SRC / "brain" / "prompts" / "learned.md"

_RULE_ID_RE = re.compile(r"^learned_[a-z0-9_]{1,80}$")
_SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,40}$")
_MAX_SNIPPET_CHARS = 2000


class ReviewError(Exception):
    pass


class GateFailed(ReviewError):
    pass


@dataclass
class ReviewOutcome:
    ok: bool
    message: str
    proposal_id: str = ""
    applied_id: Optional[int] = None


def _audit(tool: str, decision: str, reason: str, args: Optional[Dict[str, Any]] = None) -> None:
    try:
        from jarvis.policy.audit import AuditLogger

        AuditLogger(principal="learning-reviewer").log(tool, args or {}, decision, reason)
    except Exception:
        logger.exception("learning audit log failed")


def _validate_reflex_rule(rule: Dict[str, Any]) -> Dict[str, Any]:
    """Fail-closed validation of a learned reflex rule payload."""
    if not isinstance(rule, dict):
        raise ReviewError("rule payload must be an object")
    rid = rule.get("id", "")
    if not _RULE_ID_RE.match(str(rid)):
        raise ReviewError(f"bad rule id {rid!r} (must match learned_...)")
    patterns = rule.get("patterns")
    if not isinstance(patterns, list) or not patterns:
        raise ReviewError("rule needs at least one regex pattern (fill it in before approving)")
    compiled = []
    for p in patterns:
        if not isinstance(p, str) or not p.strip() or len(p) > 300:
            raise ReviewError(f"bad pattern {p!r}")
        try:
            compiled.append(re.compile(p, re.IGNORECASE))
        except re.error as e:
            raise ReviewError(f"pattern {p!r} does not compile: {e}") from e
    tool = str(rule.get("tool", ""))
    if not tool:
        raise ReviewError("rule needs a tool")
    # The critical guard: learned rules may NEVER target destructive tools.
    from jarvis.tools.registry import REGISTRY, Risk

    spec = REGISTRY.get(tool)
    if spec is None:
        raise ReviewError(f"unknown tool {tool!r}")
    if spec.risk.value > Risk.REVERSIBLE.value:
        raise ReviewError(
            f"tool {tool!r} is {spec.risk.name}: learned reflex rules are "
            f"limited to READ/REVERSIBLE tools (confirmation bypass risk)"
        )
    args = rule.get("args") or {}
    if not isinstance(args, dict):
        raise ReviewError("rule args must be an object")
    # Validate args against the tool's schema (fail-closed on bad args).
    try:
        spec.params.model_validate(args)
    except Exception as e:
        raise ReviewError(f"rule args fail {tool} schema: {e}") from e
    return {
        "id": rid,
        "patterns": [str(p) for p in patterns],
        "tool": tool,
        "args": args,
        "reply": str(rule.get("reply", ""))[:200],
        "compute": None,
    }


def _validate_prompt_snippet(body: Dict[str, Any]) -> Dict[str, str]:
    title = str(body.get("section_title", "")).strip()
    md = str(body.get("markdown", "")).strip()
    if not title or not md:
        raise ReviewError("snippet needs section_title and markdown")
    if len(md) > _MAX_SNIPPET_CHARS:
        raise ReviewError("snippet too long (>2000 chars)")
    low = md.lower()
    if "<script" in low or "javascript:" in low:
        raise ReviewError("snippet contains active content")
    return {"section_title": title[:120], "markdown": md}


def _validate_skill_variant(body: Dict[str, Any]) -> Dict[str, Any]:
    name = str(body.get("skill_name", "")).strip()
    if not _SKILL_NAME_RE.match(name):
        raise ReviewError(f"bad skill name {name!r}")
    desc = str(body.get("description", "")).strip()[:500] or "Learned composite skill (scaffold)."
    tools = body.get("suggested_tools") or []
    if not isinstance(tools, list):
        raise ReviewError("suggested_tools must be a list")
    return {
        "skill_name": name,
        "description": desc,
        "suggested_tools": [str(t)[:60] for t in tools][:10],
    }


class Reviewer:
    """Applies human decisions to proposals. Constructed with explicit
    paths so tests never touch the real repo tree."""

    def __init__(
        self,
        store: LearningStore,
        learned_rules_path: Optional[Path] = None,
        learned_prompt_path: Optional[Path] = None,
        skills_dir: Optional[Path] = None,
    ) -> None:
        self.store = store
        self.learned_rules_path = Path(learned_rules_path) if learned_rules_path else _LEARNED_RULES
        self.learned_prompt_path = (
            Path(learned_prompt_path) if learned_prompt_path else _LEARNED_PROMPT
        )
        self.skills_dir = Path(skills_dir) if skills_dir else None

    # -- read ------------------------------------------------------------
    def list(self, status: str = "") -> List[Dict[str, Any]]:
        return self.store.list_proposals(status)

    def get(self, pid: str) -> Optional[Dict[str, Any]]:
        return self.store.get_proposal(pid)

    # -- decisions ---------------------------------------------------------
    def reject(self, pid: str, reason: str = "", reviewer: str = "user") -> ReviewOutcome:
        p = self.store.get_proposal(pid)
        if p is None:
            return ReviewOutcome(False, f"unknown proposal {pid}", pid)
        if p["status"] != "pending":
            return ReviewOutcome(False, f"proposal {pid} is {p['status']}, not pending", pid)
        self.store.update_proposal(
            pid,
            status="rejected",
            decided_ts=_utcnow(),
            decided_by=reviewer,
            decision_reason=reason[:500],
        )
        _audit(
            "learning.reject",
            "allow",
            f"{pid} rejected by {reviewer}: {reason[:200]}",
            {"proposal": pid},
        )
        return ReviewOutcome(True, f"{pid} rejected", pid)

    def edit(
        self,
        pid: str,
        title: Optional[str] = None,
        body: Optional[Dict[str, Any]] = None,
        reviewer: str = "user",
    ) -> ReviewOutcome:
        p = self.store.get_proposal(pid)
        if p is None:
            return ReviewOutcome(False, f"unknown proposal {pid}", pid)
        if p["status"] != "pending":
            return ReviewOutcome(False, f"proposal {pid} is {p['status']}, not pending", pid)
        fields: Dict[str, Any] = {}
        if title is not None:
            fields["title"] = title[:300]
        if body is not None:
            # Re-validate the edited payload against the type schema.
            try:
                self._validate_payload(p["type"], body)
            except ReviewError as e:
                return ReviewOutcome(False, f"invalid payload: {e}", pid)
            fields["body"] = json.dumps(body, ensure_ascii=False)
        if not fields:
            return ReviewOutcome(False, "nothing to edit", pid)
        self.store.update_proposal(pid, **fields)
        _audit("learning.edit", "allow", f"{pid} edited by {reviewer}", {"proposal": pid})
        return ReviewOutcome(True, f"{pid} updated", pid)

    def _validate_payload(self, ptype: str, body: Dict[str, Any]) -> Dict[str, Any]:
        if ptype == "reflex_rule":
            return {"rule": _validate_reflex_rule(body.get("rule") or {})}
        if ptype == "prompt_snippet":
            return _validate_prompt_snippet(body)
        if ptype == "skill_variant":
            return _validate_skill_variant(body)
        raise ReviewError(f"unknown proposal type {ptype!r}")

    def approve(self, pid: str, reviewer: str = "user", eval_runner=None) -> ReviewOutcome:
        """Approve + eval-gate + apply. Fail-closed at every step."""
        p = self.store.get_proposal(pid)
        if p is None:
            return ReviewOutcome(False, f"unknown proposal {pid}", pid)
        if p["status"] != "pending":
            return ReviewOutcome(False, f"proposal {pid} is {p['status']}, not pending", pid)
        try:
            body = json.loads(p["body"] or "{}")
        except ValueError:
            return ReviewOutcome(False, f"{pid}: corrupt body", pid)
        try:
            clean = self._validate_payload(p["type"], body)
        except ReviewError as e:
            return ReviewOutcome(False, f"{pid}: invalid payload: {e}", pid)

        gate: EvalGateResult = run_eval_gate(p["type"], runner=eval_runner)
        self.store.update_proposal(
            pid,
            eval_report=json.dumps(
                {
                    "passed": gate.passed,
                    "subsets": gate.subsets,
                    "by_category": gate.by_category,
                    "overall_rate": gate.overall_rate,
                    "detail": gate.detail,
                },
                ensure_ascii=False,
            ),
        )
        if not gate.passed:
            _audit(
                "learning.approve",
                "deny",
                f"{pid} blocked by eval gate: {gate.detail}",
                {"proposal": pid},
            )
            return ReviewOutcome(
                False, f"{pid}: eval gate FAILED — not applied ({gate.detail})", pid
            )
        try:
            applied_id, path = self._apply(p["type"], pid, clean)
        except ReviewError as e:
            _audit("learning.approve", "deny", f"{pid} apply failed: {e}", {"proposal": pid})
            return ReviewOutcome(False, f"{pid}: apply failed: {e}", pid)

        self.store.update_proposal(
            pid,
            status="applied",
            decided_ts=_utcnow(),
            decided_by=reviewer,
            decision_reason="approved+eval-gate+applied",
        )
        _audit(
            "learning.approve",
            "allow",
            f"{pid} approved by {reviewer}, gate PASS, applied -> {path}",
            {"proposal": pid, "path": str(path)},
        )
        return ReviewOutcome(True, f"{pid} approved and applied -> {path}", pid, applied_id)

    # -- apply (allowlisted paths only) --------------------------------------
    def _apply(self, ptype: str, pid: str, clean: Dict[str, Any]) -> tuple:
        if ptype == "reflex_rule":
            return self._apply_reflex_rule(pid, clean["rule"])
        if ptype == "prompt_snippet":
            return self._apply_prompt_snippet(pid, clean)
        if ptype == "skill_variant":
            return self._apply_skill_variant(pid, clean)
        raise ReviewError(f"unknown proposal type {ptype!r}")

    def _read_rules_file(self) -> List[Dict[str, Any]]:
        try:
            data = json.loads(self.learned_rules_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _apply_reflex_rule(self, pid: str, rule: Dict[str, Any]) -> tuple:
        rules = self._read_rules_file()
        if any(r.get("id") == rule["id"] for r in rules):
            raise ReviewError(f"rule {rule['id']} already applied")
        backup = {"previous": list(rules)}  # copy BEFORE append (aliasing!)
        rules.append(rule)
        self.learned_rules_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.learned_rules_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.learned_rules_path)
        aid = self.store.record_applied(pid, "reflex_rule", str(self.learned_rules_path), backup)
        return aid, self.learned_rules_path

    def _apply_prompt_snippet(self, pid: str, clean: Dict[str, Any]) -> tuple:
        try:
            previous = self.learned_prompt_path.read_text(encoding="utf-8")
        except OSError:
            previous = ""
        backup = {"previous": previous}
        section = f"\n\n## {clean['section_title']} <!-- learned {pid} -->\n{clean['markdown']}\n"
        self.learned_prompt_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.learned_prompt_path, "a", encoding="utf-8") as f:
            f.write(section)
        aid = self.store.record_applied(
            pid, "prompt_snippet", str(self.learned_prompt_path), backup
        )
        return aid, self.learned_prompt_path

    def _apply_skill_variant(self, pid: str, clean: Dict[str, Any]) -> tuple:
        from jarvis.brain.skills.scaffold import new_skill

        skills_dir = self.skills_dir
        if skills_dir is None:
            from jarvis.core.config import get_settings

            try:
                skills_dir = Path(get_settings().brain.skills_dir)
            except Exception:
                skills_dir = Path("skills")
        name = clean["skill_name"]
        target = skills_dir / name
        if target.exists():
            raise ReviewError(f"skill dir {target} already exists")
        skills_dir.mkdir(parents=True, exist_ok=True)
        new_skill(skills_dir, name)
        # Fill in the learned description + evidence.
        md_path = target / "SKILL.md"
        text = md_path.read_text(encoding="utf-8")
        text = text.replace("<one-line description of what this skill does>", clean["description"])
        tools_note = (
            "\nSuggested composition: " + ", ".join(clean["suggested_tools"]) + "\n"
            if clean["suggested_tools"]
            else ""
        )
        text = text.replace("## Notes", "## Notes" + tools_note)
        md_path.write_text(text, encoding="utf-8")
        aid = self.store.record_applied(
            pid, "skill_variant", str(target), {"created_dir": str(target)}, reversible=True
        )
        return aid, target

    # -- revert ---------------------------------------------------------------
    def revert(self, applied_id: int, reviewer: str = "user") -> ReviewOutcome:
        rec = self.store.get_applied(applied_id)
        if rec is None:
            return ReviewOutcome(False, f"unknown applied change {applied_id}")
        if rec["reverted_ts"]:
            return ReviewOutcome(False, f"applied change {applied_id} already reverted")
        if not rec["reversible"]:
            return ReviewOutcome(False, f"applied change {applied_id} is not reversible")
        try:
            backup = json.loads(rec["backup"] or "{}")
        except ValueError:
            return ReviewOutcome(False, "corrupt backup")
        ctype, path = rec["change_type"], Path(rec["path"])
        try:
            if ctype == "reflex_rule":
                prev = backup.get("previous", [])
                path.write_text(json.dumps(prev, indent=2, ensure_ascii=False), encoding="utf-8")
            elif ctype == "prompt_snippet":
                path.write_text(backup.get("previous", ""), encoding="utf-8")
            elif ctype == "skill_variant":
                created = backup.get("created_dir")
                if created and Path(created).is_dir():
                    shutil.rmtree(Path(created))
            else:
                return ReviewOutcome(False, f"unknown change type {ctype!r}")
        except OSError as e:
            return ReviewOutcome(False, f"revert failed: {e}")
        self.store.mark_reverted(applied_id)
        self.store.update_proposal(
            rec["proposal_id"],
            status="reverted",
            decided_ts=_utcnow(),
            decided_by=reviewer,
            decision_reason="reverted by reviewer",
        )
        _audit(
            "learning.revert",
            "allow",
            f"applied change {applied_id} ({rec['proposal_id']}) reverted by {reviewer}",
            {"applied_id": applied_id},
        )
        return ReviewOutcome(
            True, f"applied change {applied_id} reverted", rec["proposal_id"], applied_id
        )
