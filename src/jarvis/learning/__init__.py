"""Self-improving skills, human-reviewed (Phase 9 moonshot).

Hermes-style learning loop, deliberately conservative:

* :mod:`jarvis.learning.store` — SQLite learning store (signals, proposals,
  applied changes). Privacy-safe: redacted args only, never raw user text.
* :mod:`jarvis.learning.recorder` — records skill executions + corrections.
  Learns NOTHING from untrusted/MCP-sourced content (poisoning guard).
* :mod:`jarvis.learning.proposer` — offline analyzer: patterns -> proposals.
  Proposals only, never auto-applied.
* :mod:`jarvis.learning.eval_gate` — eval-gated apply (fail-closed).
* :mod:`jarvis.learning.reviewer` — approve / reject / edit / revert with
  audit logging and versioned, reversible changes.
* :mod:`jarvis.learning.service` — glue with default paths.

The loop NEVER auto-applies anything: every change needs an explicit
human approval in the control center (or `jarvis learn`), behind the
same bearer-token auth as everything else.
"""

from jarvis.learning.service import LearningService

__all__ = ["LearningService"]
