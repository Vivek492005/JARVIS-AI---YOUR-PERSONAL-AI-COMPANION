"""Skill scaffolding (Task 4.6.4): `jarvis skill new <name>`."""

from __future__ import annotations

from pathlib import Path

_SKILL_MD = """---
name: {name}
description: <one-line description of what this skill does>
version: 0.1.0
permissions: []
tools:
  - {{name: {tool}, risk: reversible}}
---
## Kab use karna hai
<When should JARVIS reach for this skill?>

## Notes
<Auth, limits, gotchas. Keep secrets in the OS keyring, never in this file.>
"""

_TOOL_PY = '''"""Tool registration for the {name} skill."""

from jarvis.brain.skills.loader import _register  # noqa
'''


def new_skill(skills_dir: Path, name: str, tool_name: str = "") -> Path:
    """Create skills/<name>/SKILL.md + tool.py scaffold. Returns the dir."""
    if not name.replace("-", "").replace("_", "").isalnum():
        raise ValueError(f"bad skill name: {name!r}")
    d = skills_dir / name
    if d.exists():
        raise FileExistsError(f"skill dir already exists: {d}")
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        _SKILL_MD.format(name=name, tool=tool_name or name.replace("-", "_")),
        encoding="utf-8")
    (d / "tool.py").write_text(
        '"""Tool registration for the %s skill."""\n\n'
        '# from jarvis.tools.registry import ToolSpec, Risk, <Your>Params\n'
        '# from jarvis.tools.actions import <your_handler>\n'
        '#\n'
        '# register_skill_tool(ToolSpec(\n'
        '#     name="%s",\n'
        '#     description="...",\n'
        '#     params=<Your>Params,\n'
        '#     risk=Risk.REVERSIBLE,\n'
        '#     handler=lambda args, cb, nf: <your_handler>(...)))\n' % (name, tool_name or name.replace("-", "_")),
        encoding="utf-8")
    return d
