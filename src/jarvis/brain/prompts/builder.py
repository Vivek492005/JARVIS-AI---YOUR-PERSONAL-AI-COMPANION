"""Prompt architecture (Master Plan Task 4.3).

Layered, versioned system prompt assembled from files in this directory:

    1. IDENTITY + PERSONA   (identity.md)
    2. USER PROFILE         (workspace/USER.md + retrieved memory facts)
    3. SAFETY RULES         (safety.md)
    4. TOOL CATALOG         (auto-generated from the tool registry)
    5. LIVE CONTEXT         (time, mode, battery; clipboard = flag only)
    6. STYLE RULES          (style.md)

Rule from the plan: prompt changes go through PR + eval run (4.7) before
merge. The version constant below is bumped on every prompt change so eval
reports can pin which prompt produced a result.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Bump on every prompt-layer change. Eval reports pin this.
PROMPT_VERSION = "7.3.0"

_PROMPT_DIR = Path(__file__).resolve().parent


def _read_layer(name: str) -> str:
    path = _PROMPT_DIR / f"{name}.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as e:
        logger.warning("prompt layer %s missing: %s", name, e)
        return f"[{name} layer unavailable]"


def _read_learned_layer() -> str:
    """Optional learned-snippets layer (Phase 9 moonshot).

    Returns "" when the file is missing or has no real sections — unlike
    _read_layer, a missing learned file is normal, not a warning.
    """
    path = _PROMPT_DIR / "learned.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    # Strip HTML comments; empty (or comment-only) file => no layer.
    cleaned = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()
    return cleaned


def tool_catalog() -> str:
    """Auto-generated tool catalog from the registry (layer 4)."""
    from jarvis.tools.registry import REGISTRY, Risk

    lines = ["# TOOL CATALOG", "",
             "Call tools with JSON arguments matching their schema.",
             "Risk tiers: READ (safe), REVERSIBLE (undoable),",
             "DESTRUCTIVE (confirm first), SYSTEM (confirm first).", ""]
    for name in sorted(REGISTRY):
        if "." in name:  # sub-action tiers enforced server-side
            continue
        spec = REGISTRY[name]
        schema = spec.params.model_json_schema()
        props = ", ".join(sorted(schema.get("properties", {})))
        lines.append(f"- {name} [{spec.risk.name}]: {spec.description}")
        lines.append(f"  args: {props or '(none)'}")
    return "\n".join(lines)


def live_context(extra: Optional[Dict[str, str]] = None) -> str:
    """Layer 5: small live facts. Clipboard is a flag, never content."""
    from datetime import datetime

    ctx = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    if extra:
        ctx.update(extra)
    lines = ["# LIVE CONTEXT"]
    lines += [f"- {k}: {v}" for k, v in ctx.items()]
    return "\n".join(lines)


class PromptBuilder:
    """Assembles the layered system prompt."""

    def __init__(self, workspace: Optional[Path] = None) -> None:
        self.workspace = workspace

    def user_profile(self, memory_facts: Optional[List[str]] = None) -> str:
        lines = ["# USER PROFILE"]
        if self.workspace is not None:
            for fname in ("USER.md", "MEMORY.md"):
                p = self.workspace / fname
                if p.exists():
                    try:
                        lines.append(p.read_text(encoding="utf-8").strip())
                    except OSError:
                        pass
        if memory_facts:
            lines.append("## Remembered facts")
            lines += [f"- {f}" for f in memory_facts]
        return "\n".join(lines)

    def build(self,
              memory_facts: Optional[List[str]] = None,
              live_extra: Optional[Dict[str, str]] = None) -> str:
        """Assemble all six layers into the system prompt."""
        # Task 7.3: persona (workspace/PERSONA.md) is injected at layer 1,
        # right after the built-in identity. The persona block always ends
        # with a guard: safety (layer 3) overrides persona, never the reverse.
        from jarvis.brain.persona import load_persona
        persona_block = load_persona(self.workspace).render_prompt()
        sections = [
            _read_layer("identity"),
            persona_block,
            self.user_profile(memory_facts),
            _read_layer("safety"),
            tool_catalog(),
            live_context(live_extra),
            _read_layer("style"),
            _read_learned_layer(),  # Phase 9: human-approved snippets
            f"<!-- prompt_version={PROMPT_VERSION} -->",
        ]
        return "\n\n".join(s for s in sections if s)
