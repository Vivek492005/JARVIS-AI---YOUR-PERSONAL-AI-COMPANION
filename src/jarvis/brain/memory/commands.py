"""User control commands for memory (Task 4.4.6, rewired Phase C).

Recognized intents (checked before the LLM path):
  "yaad rakhna ..." / "remember ..."  -> propose a fact (needs confirm unless explicit)
  "bhool ja ..." / "forget ..."       -> delete matching facts
  "tumhe kya yaad hai?" / "what do you remember?" -> list facts
  "memory export"                     -> dump facts+episodes as text
  "memory delete all"                 -> confirm, then wipe

Phase C: commands now run against a
:py:class:`~jarvis.brain.memory.provider.MemoryProvider` (HybridProvider
in the agent) instead of a raw MemoryStore. For backward compatibility the
constructor still accepts a plain MemoryStore and wraps it.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Union

from jarvis.brain.memory.provider import MemoryProvider
from jarvis.brain.memory.sqlite_provider import SQLiteProvider
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
    """Executes memory control commands against a provider.

    Accepts a MemoryProvider (preferred) or a legacy MemoryStore, which is
    wrapped in a SQLiteProvider automatically.
    """

    def __init__(self, backend: Union[MemoryProvider, MemoryStore]) -> None:
        if isinstance(backend, MemoryStore):
            # Legacy callers pass a store; wrap it around the same DB file.
            backend = SQLiteProvider(backend.path)
        self.provider: MemoryProvider = backend

    def handle(self, cmd: MemoryCommand) -> str:
        if cmd.kind == "remember":
            return self._remember(cmd.payload)
        if cmd.kind == "forget":
            try:
                n = self.provider.forget(cmd.payload)
            except Exception as e:
                logger.exception("forget failed")
                return f"Bhoolne mein dikkat aayi: {e}"
            return (
                f"Bhool gaya. {n} yaadein delete ki." if n else "Us baare mein kuch yaad nahi tha."
            )
        if cmd.kind == "list":
            try:
                prof = self.provider.profile()
            except Exception as e:
                logger.exception("profile failed")
                return f"Yaadein nikaalne mein dikkat aayi: {e}"
            facts = prof.facts
            if not facts:
                return "Mujhe abhi kuch khaas yaad nahi hai."
            shown = "\n".join(f"{i + 1}. {f}" for i, f in enumerate(facts[:20]))
            return f"Mujhe ye yaad hai:\n{shown}"
        if cmd.kind == "export":
            try:
                return self.provider.export()
            except Exception as e:
                logger.exception("export failed")
                return f"Export mein dikkat aayi: {e}"
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
        try:
            mid = self.provider.add(f"{key}: {value}", {"source": "user", "kind": "explicit"})
        except Exception as e:
            logger.exception("remember failed")
            return f"Yaad nahi rakh paya: {e}"
        return f"Yaad rakh liya: {key} = {value} (#{mid})"

    def confirm_wipe(self) -> str:
        try:
            self.provider.wipe()
        except Exception as e:
            logger.exception("wipe failed")
            return f"Wipe mein dikkat aayi: {e}"
        return "Saari yaadein delete kar di."
