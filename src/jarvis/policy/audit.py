"""Task 1.7: audit log.

One JSON object per line in ``audit/YYYY-MM-DD.jsonl`` (local-only,
git-ignored). Fields: ts, principal, tool, args (redacted), decision,
reason, latency_ms, session_id.

A-09: secrets are redacted before anything hits disk — key-name matching
plus known token prefixes in values.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REDACTED = "***REDACTED***"

# Key names that always redact the value (case-insensitive, substring).
_REDACT_KEY_PARTS = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "auth",
    "credential",
    "private_key",
    "access_key",
    "session_key",
    "bearer",
    "client_secret",
)

# Values that look like issued tokens even under an innocent key name.
_REDACT_VALUE_PATTERNS = (
    re.compile(r"^sk-[A-Za-z0-9]{8,}"),  # OpenAI-style
    re.compile(r"^gh[pousr]_[A-Za-z0-9]{8,}"),  # GitHub PATs
    re.compile(r"^hf_[A-Za-z0-9]{8,}"),  # HuggingFace
    re.compile(r"^xox[bpas]-[A-Za-z0-9-]{8,}"),  # Slack
    re.compile(r"^AKIA[0-9A-Z]{16}$"),  # AWS access key id
)

_RETENTION_DAYS = 90


def _key_is_sensitive(key: str) -> bool:
    k = (key or "").lower().replace("-", "_")
    return any(part in k for part in _REDACT_KEY_PARTS)


def _value_looks_secret(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    v = value.strip()
    return any(p.match(v) for p in _REDACT_VALUE_PATTERNS)


def redact_value(key: str, value: Any) -> Any:
    """Redact one arg value if its name or shape looks secret."""
    if _key_is_sensitive(key) or _value_looks_secret(value):
        return REDACTED
    if isinstance(value, dict):
        return {k: redact_value(k, v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(key, v) for v in value]
    if isinstance(value, str) and len(value) > 200:
        return value[:200]
    return value


def redact_args(args: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Redact a tool-call arg dict for the audit log (A-09)."""
    return {k: redact_value(k, v) for k, v in (args or {}).items()}


def audit_dir(base: Optional[Path] = None) -> Path:
    return Path(base) if base else Path("audit")


class AuditLogger:
    """Writes redacted audit entries to audit/YYYY-MM-DD.jsonl."""

    def __init__(
        self, base: Optional[Path] = None, principal: str = "user", session_id: Optional[str] = None
    ):
        self.base = audit_dir(base)
        self.principal = principal
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self._pruned_today: Optional[str] = None

    def _path_for(self, day: datetime.date) -> Path:
        return self.base / f"{day.isoformat()}.jsonl"

    def log(
        self,
        tool: str,
        args: Optional[Dict[str, Any]],
        decision: str,
        reason: str = "",
        latency_ms: Optional[float] = None,
    ) -> None:
        """Append one entry. Must never break execution."""
        try:
            self.base.mkdir(parents=True, exist_ok=True)
            today = datetime.date.today().isoformat()
            if self._pruned_today != today:
                self.prune()
                self._pruned_today = today
            entry = {
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "principal": self.principal,
                "tool": tool,
                "args": redact_args(args),
                "decision": decision,
                "reason": str(reason)[:300],
                "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
                "session_id": self.session_id,
            }
            with open(self._path_for(datetime.date.today()), "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("audit log write failed")

    def prune(self, retention_days: int = _RETENTION_DAYS) -> int:
        """Delete audit files older than retention_days. Returns count."""
        removed = 0
        try:
            if not self.base.is_dir():
                return 0
            cutoff = datetime.date.today() - datetime.timedelta(days=retention_days)
            for p in self.base.glob("*.jsonl"):
                try:
                    day = datetime.date.fromisoformat(p.stem)
                except ValueError:
                    continue
                if day < cutoff:
                    p.unlink()
                    removed += 1
        except Exception:
            logger.exception("audit prune failed")
        return removed


# ---------------------------------------------------------------------------
# Query (backing the `jarvis audit` CLI)
# ---------------------------------------------------------------------------


def query(
    base: Optional[Path] = None,
    day: Optional[str] = None,
    tool: Optional[str] = None,
    decision: Optional[str] = None,
    session: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Read entries, newest first, with optional filters."""
    d = audit_dir(base)
    files = sorted(d.glob("*.jsonl"), reverse=True)
    if day:
        files = [p for p in files if p.stem == day]
    out: List[Dict[str, Any]] = []
    for p in files:
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if tool and e.get("tool") != tool:
                continue
            if decision and e.get("decision") != decision:
                continue
            if session and e.get("session_id") != session:
                continue
            out.append(e)
            if len(out) >= limit:
                return out
    return out


def stats(base: Optional[Path] = None, day: Optional[str] = None) -> Dict[str, Any]:
    entries = query(base, day=day, limit=10_000)
    by_tool: Dict[str, int] = {}
    by_decision: Dict[str, int] = {}
    for e in entries:
        by_tool[e.get("tool", "?")] = by_tool.get(e.get("tool", "?"), 0) + 1
        by_decision[e.get("decision", "?")] = by_decision.get(e.get("decision", "?"), 0) + 1
    return {"entries": len(entries), "by_tool": by_tool, "by_decision": by_decision}


# ---------------------------------------------------------------------------
# CLI: python -m access_os.audit <tail|stats|search|prune>
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="jarvis audit", description="Query the local audit log")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("tail", help="newest entries first")
    p.add_argument("--tool", default=None)
    p.add_argument(
        "--decision", default=None, choices=["allow", "deny", "confirm_requested", "confirmed"]
    )
    p.add_argument("--session", default=None)
    p.add_argument("--day", default=None, help="YYYY-MM-DD")
    p.add_argument("-n", type=int, default=20)

    p = sub.add_parser("stats", help="counts by tool and decision")
    p.add_argument("--day", default=None, help="YYYY-MM-DD")

    p = sub.add_parser("search", help="entries whose reason/args mention TEXT")
    p.add_argument("text")
    p.add_argument("-n", type=int, default=20)

    sub.add_parser("prune", help="delete audit files older than 90 days")

    a = ap.parse_args(argv)

    if a.cmd == "tail":
        entries = query(tool=a.tool, decision=a.decision, session=a.session, day=a.day, limit=a.n)
        for e in entries:
            print(
                f"{e['ts']} [{e['decision']:>16}] {e['tool']} "
                f"args={json.dumps(e['args'], ensure_ascii=False)[:120]} "
                f"({e['latency_ms']}ms)"
            )
        return 0

    if a.cmd == "stats":
        s = stats(day=a.day)
        print(f"entries: {s['entries']}")
        print("by tool:", json.dumps(s["by_tool"], indent=1))
        print("by decision:", json.dumps(s["by_decision"], indent=1))
        return 0

    if a.cmd == "search":
        needle = a.text.lower()
        hits = [
            e for e in query(limit=10_000) if needle in json.dumps(e, ensure_ascii=False).lower()
        ]
        for e in hits[: a.n]:
            print(f"{e['ts']} [{e['decision']}] {e['tool']}: {e['reason'][:100]}")
        print(f"{len(hits)} hit(s)")
        return 0

    if a.cmd == "prune":
        n = AuditLogger().prune()
        print(f"pruned {n} file(s)")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
