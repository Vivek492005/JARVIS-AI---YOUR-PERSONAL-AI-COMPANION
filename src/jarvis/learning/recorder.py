"""Learning signal collection (Phase 9 moonshot).

:class:`LearningRecorder` is the single entry point for feeding the learning
loop. Two collection paths:

1. **Explicit** — :meth:`record_run` / :meth:`record_correction`, called by
   JARVIS internals (e.g. the undo hook in ``brain/loop.py``).
2. **Batch** — :meth:`ingest_audit`, which replays redacted audit-log
   entries into the store without touching the hot execution path.

Safety properties (both paths):
* Args are stored REDACTED (same redaction as the audit log).
* Sensitive content is withheld entirely (hash only).
* Raw user utterances are NEVER stored.
* ``learnable=False`` for anything from an untrusted source — such rows are
  kept for observability but never feed proposals (poisoning guard).
* Everything is a no-op when the loop is disabled, and never raises.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from jarvis.learning.store import LearningStore

logger = logging.getLogger(__name__)

# Sources whose content must never train proposals (poisoning defense).
# Mirrors the spirit of memory.write_policy.guard_write_source.
_UNLEARNABLE_SOURCES = frozenset({"mcp", "untrusted", "web", "clipboard"})


def _args_hash(args: Dict[str, Any]) -> str:
    canon = json.dumps(args or {}, sort_keys=True, ensure_ascii=False,
                       default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def _source_trust(tool: str, source_trust: str) -> str:
    if (tool or "").startswith("mcp."):
        return "mcp"
    return source_trust or "local"


class LearningRecorder:
    def __init__(self, store: LearningStore) -> None:
        self.store = store

    # -- explicit recording ------------------------------------------------
    def record_run(self, tool: str, args: Optional[Dict[str, Any]],
                   decision: str = "", ok: Optional[bool] = None,
                   latency_ms: Optional[float] = None, path: str = "",
                   source_trust: str = "local") -> Optional[int]:
        """Record one skill/tool execution. Never raises."""
        try:
            if not self.store.is_enabled():
                return None
            return self._store_run(tool, args or {}, decision, ok,
                                   latency_ms, path, source_trust)
        except Exception:
            logger.exception("learning record_run failed")
            return None

    def _store_run(self, tool: str, args: Dict[str, Any], decision: str,
                   ok: Optional[bool], latency_ms: Optional[float],
                   path: str, source_trust: str) -> int:
        from jarvis.policy.audit import redact_args
        from jarvis.brain.memory.write_policy import contains_sensitive

        redacted = redact_args(args)
        probe = json.dumps(redacted, ensure_ascii=False, default=str)
        sensitive_hit = contains_sensitive(probe)
        trust = _source_trust(tool, source_trust)
        learnable = trust not in _UNLEARNABLE_SOURCES
        if sensitive_hit:
            # Withhold content entirely: hash of the redacted form survives
            # for dedup/counting, nothing readable is stored.
            redacted = {}
            withheld = True
        else:
            withheld = False
        return self.store.add_run(
            tool=tool, args_redacted=redacted,
            args_hash=_args_hash(redacted), decision=decision, ok=ok,
            latency_ms=latency_ms, path=path, source_trust=trust,
            learnable=learnable, withheld=withheld)

    def record_correction(self, kind: str, tool: str,
                          args: Optional[Dict[str, Any]] = None,
                          note: str = "") -> Optional[int]:
        """Record a user correction (undo / explicit correction / decline).

        ``kind`` in {"undo", "user_correction", "confirm_decline"}.
        """
        try:
            if not self.store.is_enabled():
                return None
            if kind not in ("undo", "user_correction", "confirm_decline"):
                logger.warning("learning: bad correction kind %r", kind)
                return None
            return self.store.add_correction(
                kind=kind, tool=tool or "",
                args_hash=_args_hash(args or {}), note=note)
        except Exception:
            logger.exception("learning record_correction failed")
            return None

    # -- batch ingestion from the audit log --------------------------------
    def ingest_audit(self, entries: List[Dict[str, Any]]) -> int:
        """Replay redacted audit entries into the store.

        Audit args are ALREADY redacted by the audit logger, so this path
        re-checks sensitivity but never sees raw content. Entries from
        untrusted tools are stored with learnable=False.
        """
        n = 0
        try:
            if not self.store.is_enabled():
                return 0
            for e in entries or []:
                tool = str(e.get("tool", ""))
                if not tool or tool.startswith("learning."):
                    continue  # never learn from our own control-plane
                args = e.get("args") or {}
                if not isinstance(args, dict):
                    args = {}
                decision = str(e.get("decision", ""))
                ok = True if decision == "allow" else (
                    False if decision == "deny" else None)
                lat = e.get("latency_ms")
                try:
                    lat = float(lat) if lat is not None else None
                except (TypeError, ValueError):
                    lat = None
                self._store_run(tool, args, decision, ok, lat,
                                path="", source_trust="local")
                n += 1
        except Exception:
            logger.exception("learning ingest_audit failed")
        return n


# ---------------------------------------------------------------------------
# Module-level hook used by brain/loop.py's UndoJournal (guarded, no-op
# when disabled or on any error — the undo path must never break).
# ---------------------------------------------------------------------------

_recorder: Optional[LearningRecorder] = None


def record_undo_event(tool: str, args: Optional[Dict[str, Any]],
                      desc: str = "") -> None:
    """Record that the user undid something. Never raises."""
    global _recorder
    try:
        if _recorder is None:
            _recorder = LearningRecorder(LearningStore())
        _recorder.record_correction("undo", tool, args, note=desc)
    except Exception:  # noqa: S110 - the undo path must never break
        pass
