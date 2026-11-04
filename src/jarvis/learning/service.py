"""Glue for the learning loop (Phase 9 moonshot).

:class:`LearningService` bundles the store, recorder, proposer and
reviewer with sensible default paths. The control center and CLI use
this; tests construct the pieces directly with tmp paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from jarvis.learning.eval_gate import EvalGateResult, run_eval_gate
from jarvis.learning.proposer import generate_proposals
from jarvis.learning.recorder import LearningRecorder
from jarvis.learning.reviewer import Reviewer
from jarvis.learning.store import LearningStore


def _default_db() -> Path:
    return Path.home() / ".jarvis" / "learning.db"


class LearningService:
    def __init__(self, db_path: Optional[Path] = None,
                 skills_dir: Optional[Path] = None) -> None:
        self.store = LearningStore(db_path or _default_db())
        self.recorder = LearningRecorder(self.store)
        self.reviewer = Reviewer(self.store, skills_dir=skills_dir)

    @classmethod
    def default(cls) -> "LearningService":
        return cls()

    # -- status ---------------------------------------------------------
    def status(self) -> dict:
        pending = self.store.list_proposals("pending")
        return {
            "enabled": self.store.is_enabled(),
            "pending_proposals": len(pending),
            "total_runs": self.store.count_runs(),
            "total_corrections": self.store.count_corrections(),
            "learnable_runs": self.store.count_runs(learnable_only=True),
        }

    def set_enabled(self, enabled: bool) -> dict:
        self.store.set_enabled(enabled)
        return {"enabled": self.store.is_enabled()}

    # -- analysis ---------------------------------------------------------
    def analyze(self, min_evidence: int = 3) -> dict:
        from jarvis.learning.proposer import DEFAULT_MIN_EVIDENCE
        return generate_proposals(
            self.store, min_evidence or DEFAULT_MIN_EVIDENCE)

    def ingest_audit(self, limit: int = 2000) -> dict:
        from jarvis.policy import audit
        entries = audit.query(limit=limit)
        n = self.recorder.ingest_audit(entries)
        return {"ingested": n}

    # -- review (delegated) ----------------------------------------------
    def approve(self, pid: str, reviewer: str = "user",
                eval_runner=None):
        return self.reviewer.approve(pid, reviewer, eval_runner)

    def eval_gate(self, proposal_type: str,
                  eval_runner=None) -> EvalGateResult:
        return run_eval_gate(proposal_type, runner=eval_runner)
