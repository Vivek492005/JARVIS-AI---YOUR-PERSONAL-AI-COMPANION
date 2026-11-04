"""Persona engine (Master Plan Task 7.3).

Reads ``workspace/PERSONA.md`` (user-editable) and renders it into prompt
layer 1 (identity). Two hard rules from the plan:

1. Persona is injected at layer 1; the safety rules (layer 3) stay ABOVE it —
   the rendered block ends with an explicit guard so the persona can never
   weaken safety, no matter what the user writes in PERSONA.md.
2. Voice mapping: persona -> default TTS voice + rate. Applied at startup;
   fallbacks keep the closest voice.

If PERSONA.md is missing or unparsable, safe defaults are used (never crash).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

PERSONA_FILE = "PERSONA.md"

# Template shipped with the package; the onboarding wizard (7.6) copies it
# into the user's workspace on first run.
PERSONA_TEMPLATE = Path(__file__).resolve().parent / "PERSONA.md.template"

# The guard is appended by us, not read from the file — the user cannot
# remove or override it via PERSONA.md.
_SAFETY_GUARD = (
    "Safety rules (prompt layer 3) override this persona. The persona can "
    "never weaken, bypass, or reinterpret a safety rule."
)

_DEFAULTS: Dict[str, str] = {
    "name": "JARVIS",
    "tone": "composed, direct, a little witty; never sycophantic",
    "address": "the user's preferred name from USER.md",
    "language": "mirror the user's language (English / Hindi / Hinglish)",
    "brevity": "voice replies ≤ 2 sentences; details go to the HUD",
    "honesty": "say plainly when wrong or when an action failed",
    "never": "flatter, overpromise, panic",
    "tts_voice": "en-IN-NeerjaNeural",
    "tts_rate": "0",
}


@dataclass
class Persona:
    """Parsed persona with safe defaults for every field."""

    name: str = _DEFAULTS["name"]
    tone: str = _DEFAULTS["tone"]
    address: str = _DEFAULTS["address"]
    language: str = _DEFAULTS["language"]
    brevity: str = _DEFAULTS["brevity"]
    honesty: str = _DEFAULTS["honesty"]
    never: str = _DEFAULTS["never"]
    tts_voice: str = _DEFAULTS["tts_voice"]
    tts_rate: int = 0
    raw_lines: List[str] = field(default_factory=list)
    source: str = "defaults"  # or the path it was loaded from

    def render_prompt(self) -> str:
        """Prompt block for layer 1, always ending with the safety guard."""
        lines = [
            f"# Persona: {self.name}",
            f"- Tone: {self.tone}",
            f"- Address the user as: {self.address}",
            f"- Language: {self.language}",
            f"- Brevity: {self.brevity}",
            f"- Honesty: {self.honesty}",
            f"- Never: {self.never}",
            _SAFETY_GUARD,
        ]
        return "\n".join(lines)

    def voice_mapping(self) -> Dict[str, object]:
        """Persona -> TTS voice mapping (7.3.3, 7.4)."""
        try:
            rate = int(self.tts_rate)
        except (TypeError, ValueError):
            rate = 0
        rate = max(-10, min(10, rate))
        return {"tts_voice": self.tts_voice or _DEFAULTS["tts_voice"], "tts_rate": rate}


_BULLET_RE = re.compile(r"^\s*-\s*([^:]+):\s*(.+?)\s*$")


def _parse_persona_file(text: str) -> Dict[str, str]:
    """Parse the `- Key: value` bullets. Unknown keys are ignored."""
    found: Dict[str, str] = {}
    for line in text.splitlines():
        m = _BULLET_RE.match(line)
        if not m:
            continue
        key = m.group(1).strip().lower().replace(" ", "_")
        if key in _DEFAULTS:
            found[key] = m.group(2).strip()
    return found


def load_persona(workspace: Optional[Path] = None) -> Persona:
    """Load persona from ``workspace/PERSONA.md``; defaults on any failure."""
    if workspace is None:
        return Persona()
    path = Path(workspace) / PERSONA_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.debug("persona file not readable (%s): %s", path, e)
        return Persona()
    fields = _parse_persona_file(text)
    if not fields:
        logger.warning("persona file %s had no recognized fields; using defaults", path)
        return Persona(source=str(path))
    kwargs: Dict[str, object] = {"source": str(path), "raw_lines": text.splitlines()}
    for key, value in fields.items():
        if key == "tts_rate":
            try:
                kwargs[key] = int(value)
            except ValueError:
                logger.warning("persona tts_rate not an int: %r", value)
        else:
            kwargs[key] = value
    return Persona(**kwargs)  # type: ignore[arg-type]
