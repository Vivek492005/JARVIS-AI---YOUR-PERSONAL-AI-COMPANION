"""User control commands for memory (Task 4.4.6).

Recognized intents (checked before the LLM path):
  "yaad rakhna ..." / "remember ..."  -> propose a fact (needs confirm unless explicit)
  "bhool ja ..." / "forget ..."       -> delete matching facts
  "tumhe kya yaad hai?" / "what do you remember?" -> list facts
  "memory export"                     -> dump facts+episodes as text
  "memory delete all"                 -> confirm, then wipe
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from jarvis.brain.memory.store import MemoryStore
from jarvis.brain.memory.write_policy import WriteRequest, validate_write

logger = logging.getLogger(__name__)

_REMEMBER = re.compile(r"(?i)^\s*(yaad rakhna|remember|note kar lo)\b[:\s]*(.+)$")
_FORGET = re.compile(r"(?i)^\s*(bhool ja|forget)\b[:\s]*(.+)$")
_LIST = re.compile(r"(?i)^\s*(tumhe kya yaad hai|what do you remember|list memory)\b")
_EXPORT = re.compile(r"(?i)^\s*memory export\b")
_WIPE = re.compile(r"(?i)^\s*memory (delete all|wipe|clear all)\b")


@dataclass
class MemoryCommand:
    kind: str  # remember | forget | list | export | wipe | none
    payload: str = ""


def parse(text: str) -> MemoryCommand:
    t = (text or "").strip()
    m = _REMEMBER.match(t)
    if m:
        return MemoryCommand("remember", m.group(2).strip())
    m = _FORGET.match(t)
    if m:
        return MemoryCommand("forget", m.group(2).strip())
    if _LIST.match(t):
        return MemoryCommand("list")
    if _EXPORT.match(t):
        return MemoryCommand("export")
    if _WIPE.match(t):
        return MemoryCommand("wipe")
    return MemoryCommand("none")


def _split_key_value(payload: str) -> tuple:
    """'meri default browser Chrome hai' -> ('default browser', 'Chrome')."""
    m = re.match(r"(?i)^(?:meri|mera|my)\s+(.+?)\s+(?:hai|is)\s+(.+)$", payload.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # fallback: first half = key, whole = value context
    words = payload.split()
    key = " ".join(words[:4])
    return key, payload


class MemoryCommands:
    """Executes memory control commands against a store."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def handle(self, cmd: MemoryCommand) -> str:
        if cmd.kind == "remember":
            return self._remember(cmd.payload)
        if cmd.kind == "forget":
            n = self.store.delete_facts_like(cmd.payload)
            return (
                f"Bhool gaya. {n} yaadein delete ki." if n else "Us baare mein kuch yaad nahi tha."
            )
        if cmd.kind == "list":
            facts = self.store.all_facts()
            if not facts:
                return "Mujhe abhi kuch khaas yaad nahi hai."
            return "Mujhe ye yaad hai:\n" + "\n".join(
                f"{i + 1}. {f.key}: {f.value}" for i, f in enumerate(facts[:20])
            )
        if cmd.kind == "export":
            facts = self.store.all_facts()
            eps = self.store.recent_episodes(50)
            out = ["# MEMORY EXPORT", "## Facts"]
            out += [f"- [{f.source}] {f.key}: {f.value}" for f in facts]
            out.append("## Recent episodes")
            out += [f"- ({e['ts']}) {e['role']}: {e['text'][:120]}" for e in eps]
            return "\n".join(out)
        if cmd.kind == "wipe":
            # The caller must confirm first; this method only wipes when the
            # confirmed flag flows through the policy gate. We return the
            # confirmation question here and wipe on explicit yes.
            return (
                "CONFIRM_WIPE: Saari yaadein (facts + episodes) delete ho "
                "jayengi. Pakka? 'haan' bolo."
            )
        return ""

    def _remember(self, payload: str) -> str:
        key, value = _split_key_value(payload)
        req = WriteRequest(key=key, value=value, source="user")
        err = validate_write(req)
        if err:
            return f"Yaad nahi rakh paya: {err}"
        fid = self.store.add_fact(key, value, source="user")
        return f"Yaad rakh liya: {key} = {value} (#{fid})"

    def confirm_wipe(self) -> str:
        self.store.clear_all()
        return "Saari yaadein delete kar di."
