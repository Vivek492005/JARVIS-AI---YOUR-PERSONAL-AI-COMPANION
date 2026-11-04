"""Learning store (Phase 9 moonshot): SQLite signal + proposal storage.

Privacy model (deliberate):
* Tool args are stored REDACTED via :func:`jarvis.policy.audit.redact_args`
  (same redaction as the audit log).
* If the redacted text still matches a sensitive pattern
  (:func:`jarvis.brain.memory.write_policy.contains_sensitive`), the content
  is withheld entirely — only a hash survives for dedup/counting.
* Raw user utterances are NEVER stored. Learned reflex patterns are left
  blank for the human reviewer to fill in (see proposer).

Poisoning model:
* Rows carry ``source_trust`` (``local`` | ``third_party`` | ``mcp`` |
  ``untrusted`` | ``web``) and a ``learnable`` flag. Anything from an
  untrusted source is recorded for observability but NEVER feeds proposals.
"""

from __future__ import annotations

import datetime
import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS skill_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    tool          TEXT NOT NULL,
    args_redacted TEXT NOT NULL DEFAULT '{}',
    args_hash     TEXT NOT NULL DEFAULT '',
    decision      TEXT NOT NULL DEFAULT '',
    ok            INTEGER,              -- 1 = verified ok, 0 = failed/denied, NULL = unknown
    latency_ms    REAL,
    path          TEXT NOT NULL DEFAULT '',   -- reflex | llm | '' (unknown)
    source_trust  TEXT NOT NULL DEFAULT 'local',
    learnable     INTEGER NOT NULL DEFAULT 1,
    withheld      INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS corrections (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    kind      TEXT NOT NULL,            -- undo | user_correction | confirm_decline
    tool      TEXT NOT NULL,
    args_hash TEXT NOT NULL DEFAULT '',
    note      TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS proposals (
    id             TEXT PRIMARY KEY,    -- LP-0001, ...
    type           TEXT NOT NULL,       -- reflex_rule | prompt_snippet | skill_variant
    target         TEXT NOT NULL DEFAULT '',
    title          TEXT NOT NULL,
    body           TEXT NOT NULL DEFAULT '{}',   -- JSON payload (diff/preview)
    evidence       TEXT NOT NULL DEFAULT '{}',   -- JSON (counts, examples)
    confidence     REAL NOT NULL DEFAULT 0.0,
    status         TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|applied|rejected|reverted
    created_ts     TEXT NOT NULL,
    decided_ts     TEXT,
    decided_by     TEXT,
    decision_reason TEXT,
    eval_report    TEXT                      -- JSON, set when the gate runs
);
CREATE TABLE IF NOT EXISTS applied (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL,
    ts          TEXT NOT NULL,
    change_type TEXT NOT NULL,
    path        TEXT NOT NULL,
    backup      TEXT,                   -- JSON: previous content or marker
    reversible  INTEGER NOT NULL DEFAULT 1,
    reverted_ts TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_tool_ts ON skill_runs(tool, ts);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
"""


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")


class LearningStore:
    """Thread-safe SQLite store for the learning loop."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else (
            Path.home() / ".jarvis" / "learning.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        if self._get_meta("enabled") is None:
            self._set_meta("enabled", "1")
        if self._get_meta("proposal_seq") is None:
            self._set_meta("proposal_seq", "0")

    # -- meta -----------------------------------------------------------
    def _get_meta(self, key: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def _set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value))
            self._conn.commit()

    def is_enabled(self) -> bool:
        return self._get_meta("enabled") == "1"

    def set_enabled(self, enabled: bool) -> None:
        self._set_meta("enabled", "1" if enabled else "0")

    def next_proposal_id(self) -> str:
        with self._lock:
            seq = int(self._get_meta("proposal_seq") or "0") + 1
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES('proposal_seq', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(seq),))
            self._conn.commit()
        return f"LP-{seq:04d}"

    # -- skill runs ------------------------------------------------------
    def add_run(self, tool: str, args_redacted: Dict[str, Any],
                args_hash: str, decision: str = "",
                ok: Optional[bool] = None,
                latency_ms: Optional[float] = None, path: str = "",
                source_trust: str = "local", learnable: bool = True,
                withheld: bool = False) -> int:
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO skill_runs
                   (ts, tool, args_redacted, args_hash, decision, ok,
                    latency_ms, path, source_trust, learnable, withheld)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (_utcnow(), tool, json.dumps(args_redacted,
                                             ensure_ascii=False),
                 args_hash, decision,
                 None if ok is None else (1 if ok else 0),
                 latency_ms, path, source_trust,
                 1 if learnable else 0, 1 if withheld else 0))
            self._conn.commit()
            return int(cur.lastrowid)

    def count_runs(self, learnable_only: bool = False) -> int:
        q = "SELECT COUNT(*) AS n FROM skill_runs"
        if learnable_only:
            q += " WHERE learnable=1"
        with self._lock:
            row = self._conn.execute(q).fetchone()
        return int(row["n"])

    def count_corrections(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM corrections").fetchone()
        return int(row["n"])

    def recent_runs(self, limit: int = 500,
                    learnable_only: bool = True) -> List[Dict[str, Any]]:
        if learnable_only:
            q = ("SELECT * FROM skill_runs WHERE learnable=1 "
                 "ORDER BY id DESC LIMIT ?")
        else:
            q = "SELECT * FROM skill_runs ORDER BY id DESC LIMIT ?"
        with self._lock:
            rows = self._conn.execute(q, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def run_clusters(self, min_count: int = 3,
                     since_days: int = 30) -> List[Dict[str, Any]]:
        """Clusters of repeated (tool, args_hash) executions.

        The evidence base for reflex_rule proposals: the same tool called
        with the same (hashed) args again and again is a reflex candidate.
        """
        cutoff = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(days=since_days)).isoformat()
        with self._lock:
            rows = self._conn.execute(
                """SELECT tool, args_hash, args_redacted, COUNT(*) AS n,
                          SUM(CASE WHEN decision='allow' THEN 1 ELSE 0 END) AS n_allow
                   FROM skill_runs
                   WHERE learnable=1 AND ts >= ?
                   GROUP BY tool, args_hash
                   HAVING COUNT(*) >= ?
                   ORDER BY n DESC""",
                (cutoff, min_count)).fetchall()
        return [dict(r) for r in rows]

    def correction_clusters(self, min_count: int = 2,
                            since_days: int = 30) -> List[Dict[str, Any]]:
        """Tools with repeated corrections — prompt_snippet candidates."""
        cutoff = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(days=since_days)).isoformat()
        with self._lock:
            rows = self._conn.execute(
                """SELECT tool, kind, COUNT(*) AS n
                   FROM corrections
                   WHERE ts >= ?
                   GROUP BY tool, kind
                   HAVING COUNT(*) >= ?
                   ORDER BY n DESC""",
                (cutoff, min_count)).fetchall()
        return [dict(r) for r in rows]

    def tool_sequences(self, min_count: int = 3,
                       since_days: int = 30) -> List[Dict[str, Any]]:
        """Frequent A->B tool bigrams — skill_variant candidates.

        Uses row order (id) as a proxy for temporal adjacency; bigrams are
        only counted when consecutive rows are close in time (< 5 min).
        """
        cutoff = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(days=since_days)).isoformat()
        with self._lock:
            rows = self._conn.execute(
                """SELECT tool, ts FROM skill_runs
                   WHERE learnable=1 AND decision='allow' AND ts >= ?
                   ORDER BY id ASC""",
                (cutoff,)).fetchall()
        counts: Dict[str, int] = {}
        prev_tool: Optional[str] = None
        prev_ts: Optional[datetime.datetime] = None
        for r in rows:
            try:
                ts = datetime.datetime.fromisoformat(r["ts"])
            except ValueError:
                prev_tool, prev_ts = None, None
                continue
            if (prev_tool and prev_tool != r["tool"] and prev_ts
                    and (ts - prev_ts).total_seconds() < 300):
                key = f"{prev_tool} -> {r['tool']}"
                counts[key] = counts.get(key, 0) + 1
            prev_tool, prev_ts = r["tool"], ts
        return [{"sequence": k, "n": v} for k, v in
                sorted(counts.items(), key=lambda kv: -kv[1])
                if v >= min_count]

    # -- corrections ------------------------------------------------------
    def add_correction(self, kind: str, tool: str, args_hash: str = "",
                       note: str = "") -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO corrections (ts, kind, tool, args_hash, note)"
                " VALUES (?, ?, ?, ?, ?)",
                (_utcnow(), kind, tool, args_hash, note[:500]))
            self._conn.commit()
            return int(cur.lastrowid)

    # -- proposals ---------------------------------------------------------
    def add_proposal(self, ptype: str, target: str, title: str,
                     body: Dict[str, Any], evidence: Dict[str, Any],
                     confidence: float) -> str:
        pid = self.next_proposal_id()
        with self._lock:
            self._conn.execute(
                """INSERT INTO proposals
                   (id, type, target, title, body, evidence, confidence,
                    status, created_ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                (pid, ptype, target, title,
                 json.dumps(body, ensure_ascii=False),
                 json.dumps(evidence, ensure_ascii=False),
                 confidence, _utcnow()))
            self._conn.commit()
        return pid

    def get_proposal(self, pid: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
        return dict(row) if row else None

    def list_proposals(self, status: str = "") -> List[Dict[str, Any]]:
        q = "SELECT * FROM proposals "
        args: tuple = ()
        if status:
            q += "WHERE status=? "
            args = (status,)
        q += "ORDER BY id DESC"
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
        return [dict(r) for r in rows]

    def update_proposal(self, pid: str, **fields) -> bool:
        allowed = {"title", "body", "status", "decided_ts", "decided_by",
                   "decision_reason", "eval_report", "confidence"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return False
        cols = ", ".join(f"{k}=?" for k in sets)
        with self._lock:
            # S608: cols is built from the `allowed` allowlist above, and
            # values are bound parameters — no injection surface.
            query = f"UPDATE proposals SET {cols} WHERE id=?"  # noqa: S608
            cur = self._conn.execute(query, (*sets.values(), pid))
            self._conn.commit()
            return cur.rowcount > 0

    def proposal_exists_for(self, ptype: str, target: str) -> bool:
        """Avoid duplicate pending proposals for the same target."""
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM proposals WHERE type=? AND target=? "
                "AND status IN ('pending','approved') LIMIT 1",
                (ptype, target)).fetchone()
        return row is not None

    # -- applied changes ----------------------------------------------------
    def record_applied(self, proposal_id: str, change_type: str, path: str,
                       backup: Dict[str, Any],
                       reversible: bool = True) -> int:
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO applied
                   (proposal_id, ts, change_type, path, backup, reversible)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (proposal_id, _utcnow(), change_type, path,
                 json.dumps(backup, ensure_ascii=False),
                 1 if reversible else 0))
            self._conn.commit()
            return int(cur.lastrowid)

    def get_applied(self, aid: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM applied WHERE id=?", (aid,)).fetchone()
        return dict(row) if row else None

    def list_applied(self, include_reverted: bool = True) -> List[Dict[str, Any]]:
        q = "SELECT * FROM applied "
        if not include_reverted:
            q += "WHERE reverted_ts IS NULL "
        q += "ORDER BY id DESC"
        with self._lock:
            rows = self._conn.execute(q).fetchall()
        return [dict(r) for r in rows]

    def mark_reverted(self, aid: int) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE applied SET reverted_ts=? WHERE id=? "
                "AND reverted_ts IS NULL",
                (_utcnow(), aid))
            self._conn.commit()
            return cur.rowcount > 0

    def close(self) -> None:
        with self._lock:
            self._conn.close()
