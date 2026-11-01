"""Memory store (Master Plan Task 4.4): SQLite-backed episodic + semantic layers.

Schema follows the plan exactly:

    episodes(id, ts, session, role, text, tool, outcome)
    facts(id, ts, key, value, source, importance, last_used, expires)

``source`` is CHECK-constrained to ('user','confirmed') — memory-poisoning
defense: nothing from web/file content can be written without the user (or
their explicit confirmation) as the source.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes(
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  session TEXT NOT NULL DEFAULT '',
  role TEXT NOT NULL DEFAULT '',
  text TEXT NOT NULL DEFAULT '',
  tool TEXT NOT NULL DEFAULT '',
  outcome TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS facts(
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  source TEXT NOT NULL CHECK(source IN ('user','confirmed')),
  importance REAL NOT NULL DEFAULT 0.5,
  last_used TEXT NOT NULL DEFAULT '',
  expires TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(key);
CREATE INDEX IF NOT EXISTS idx_episodes_ts ON episodes(ts);
"""


@dataclass
class Fact:
    id: int
    key: str
    value: str
    source: str
    importance: float
    last_used: str
    expires: str


class MemoryStore:
    """SQLite memory store. One file per install (default: data dir)."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or _default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S")

    # -- episodes ------------------------------------------------------

    def add_episode(self, role: str, text: str, session: str = "",
                    tool: str = "", outcome: str = "") -> int:
        cur = self._conn.execute(
            "INSERT INTO episodes(ts, session, role, text, tool, outcome)"
            " VALUES (?,?,?,?,?,?)",
            (self._now(), session, role, text, tool, outcome))
        self._conn.commit()
        return int(cur.lastrowid)

    def recent_episodes(self, limit: int = 20) -> List[sqlite3.Row]:
        return list(self._conn.execute(
            "SELECT * FROM episodes ORDER BY id DESC LIMIT ?", (limit,)))

    def episodes_since(self, ts: str) -> List[sqlite3.Row]:
        return list(self._conn.execute(
            "SELECT * FROM episodes WHERE ts >= ? ORDER BY id", (ts,)))

    # -- facts ---------------------------------------------------------

    def add_fact(self, key: str, value: str, source: str,
                 importance: float = 0.5, expires: str = "") -> int:
        if source not in ("user", "confirmed"):
            raise ValueError(f"bad fact source: {source!r}")
        cur = self._conn.execute(
            "INSERT INTO facts(ts, key, value, source, importance, last_used, expires)"
            " VALUES (?,?,?,?,?,?,?)",
            (self._now(), key, value, source, importance, self._now(), expires))
        self._conn.commit()
        return int(cur.lastrowid)

    def delete_fact(self, fact_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM facts WHERE id=?", (fact_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def delete_facts_like(self, text: str) -> int:
        """Delete facts whose key or value matches; returns count removed."""
        cur = self._conn.execute(
            "DELETE FROM facts WHERE key LIKE ? OR value LIKE ?",
            (f"%{text}%", f"%{text}%"))
        self._conn.commit()
        return cur.rowcount

    def all_facts(self) -> List[Fact]:
        rows = self._conn.execute("SELECT * FROM facts ORDER BY importance DESC")
        return [Fact(id=r["id"], key=r["key"], value=r["value"],
                     source=r["source"], importance=r["importance"],
                     last_used=r["last_used"], expires=r["expires"]) for r in rows]

    def touch_fact(self, fact_id: int, importance: Optional[float] = None) -> None:
        if importance is None:
            self._conn.execute(
                "UPDATE facts SET last_used=? WHERE id=?", (self._now(), fact_id))
        else:
            self._conn.execute(
                "UPDATE facts SET last_used=?, importance=? WHERE id=?",
                (self._now(), importance, fact_id))
        self._conn.commit()

    def purge_expired(self) -> int:
        cur = self._conn.execute(
            "DELETE FROM facts WHERE expires != '' AND expires < ?", (self._now(),))
        self._conn.commit()
        return cur.rowcount

    def clear_all(self) -> None:
        self._conn.execute("DELETE FROM episodes")
        self._conn.execute("DELETE FROM facts")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def _default_path() -> Path:
    base = Path.home() / ".jarvis"
    return base / "memory.db"
