"""Skill loader (Task 4.6): SKILL.md manifest -> validated tools -> registry.

Folder layout::

    skills/<name>/
        SKILL.md      # frontmatter: name, description, version, permissions, tools
        tool.py       # registers ToolSpec(s); may import shared handlers

Loading steps: parse frontmatter -> validate manifest -> show permissions
-> register each tool into the registry at the manifest's risk tier
(third-party skills default to DESTRUCTIVE unless the manifest says
otherwise AND the user confirmed the lower tier).
"""

from __future__ import annotations

import importlib.util
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from jarvis.brain.skills.trust import TrustLevel, sha256_of
from jarvis.tools.registry import REGISTRY, Risk, ToolSpec, tool

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class SkillToolDecl:
    name: str
    risk: str = "reversible"


@dataclass
class SkillManifest:
    name: str
    description: str
    version: str = "0.1.0"
    permissions: List[str] = field(default_factory=list)
    tools: List[SkillToolDecl] = field(default_factory=list)
    trust: TrustLevel = TrustLevel.THIRD_PARTY


def _parse_frontmatter(text: str) -> Dict[str, str]:
    m = _FRONTMATTER_RE.match(text or "")
    if not m:
        raise ValueError("SKILL.md needs a YAML frontmatter block (--- ... ---)")
    out: Dict[str, str] = {}
    current_key: Optional[str] = None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        # Continuation line (indented list item) belongs to the current key.
        if current_key and (line.startswith(" ") or line.startswith("\t") or
                            line.lstrip().startswith("-")):
            out[current_key] += "\n" + line.strip()
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            current_key = k.strip()
            out[current_key] = v.strip().strip("\"'")
        else:
            current_key = None
    return out


def _parse_tools(raw: str) -> List[SkillToolDecl]:
    # tools: [{name: x, risk: reversible}, ...]  or  tools: [x, y]
    decls = []
    for m in re.finditer(r"name\s*:\s*([a-z_0-9]+)", raw):
        risk_m = re.search(r"risk\s*:\s*([a-z_]+)", raw[m.start():m.start() + 120])
        decls.append(SkillToolDecl(name=m.group(1),
                                   risk=risk_m.group(1) if risk_m else "reversible"))
    if not decls:
        for name in re.findall(r"([a-z_0-9]+)", raw):
            if name not in ("tools",):
                decls.append(SkillToolDecl(name=name))
    return decls


def load_manifest(skill_dir: Path) -> SkillManifest:
    md = skill_dir / "SKILL.md"
    if not md.exists():
        raise FileNotFoundError(f"{skill_dir} has no SKILL.md")
    fm = _parse_frontmatter(md.read_text(encoding="utf-8"))
    for req in ("name", "description"):
        if not fm.get(req):
            raise ValueError(f"SKILL.md missing required field: {req}")
    return SkillManifest(
        name=fm["name"],
        description=fm["description"],
        version=fm.get("version", "0.1.0"),
        permissions=[p.strip() for p in fm.get("permissions", "").split(",") if p.strip()],
        tools=_parse_tools(fm.get("tools", "")),
    )


def _risk_for(manifest: SkillManifest, decl: SkillToolDecl) -> Risk:
    """Third-party skills default to DESTRUCTIVE (fail-closed)."""
    try:
        wanted = Risk[decl.risk.upper()]
    except KeyError:
        wanted = Risk.REVERSIBLE
    if manifest.trust == TrustLevel.THIRD_PARTY and wanted.value < Risk.DESTRUCTIVE.value:
        logger.warning("skill %s: third-party tool %s forced to DESTRUCTIVE",
                       manifest.name, decl.name)
        return Risk.DESTRUCTIVE
    return wanted


def load_skill(skill_dir: Path, trust: TrustLevel = TrustLevel.THIRD_PARTY,
               confirm_lower_risk: bool = False) -> SkillManifest:
    """Load one skill: validate manifest, show permissions, import tool.py.

    ``tool.py`` must call ``register_skill_tool(...)`` for each declared
    tool. Returns the manifest.
    """
    manifest = load_manifest(skill_dir)
    manifest.trust = trust
    # Phase 5.10: untrusted (third-party) skills need sandbox Level B+.
    try:
        from jarvis.perception.sandbox import assert_skill_allowed
        assert_skill_allowed(manifest.name, manifest.trust.value
                             if hasattr(manifest.trust, "value")
                             else str(manifest.trust))
    except PermissionError:
        raise
    if manifest.permissions:
        logger.info("skill '%s' requests permissions: %s",
                    manifest.name, ", ".join(manifest.permissions))
    tool_py = skill_dir / "tool.py"
    if tool_py.exists():
        spec = importlib.util.spec_from_file_location(
            f"jarvis_skill_{manifest.name}", str(tool_py))
        mod = importlib.util.module_from_spec(spec)
        # Inject the registration helper before exec.
        mod.register_skill_tool = lambda spec, _m=manifest: _register(manifest, spec)  # noqa: E731
        spec.loader.exec_module(mod)
    return manifest


def _register(manifest: SkillManifest, spec: ToolSpec) -> ToolSpec:
    if spec.name in REGISTRY:
        logger.debug("skill %s: tool %s already registered, skipping",
                     manifest.name, spec.name)
        return REGISTRY[spec.name]
    # Enforce the trust risk floor.
    floor = Risk.DESTRUCTIVE if manifest.trust == TrustLevel.THIRD_PARTY else Risk.READ
    if spec.risk.value < floor.value:
        spec = ToolSpec(name=spec.name, description=spec.description,
                        params=spec.params, risk=floor, handler=spec.handler,
                        timeout_s=spec.timeout_s, scopes=spec.scopes,
                        carries_external_data=spec.carries_external_data)
    return tool(spec)


def load_all(skills_dir: Path, local_names: frozenset = frozenset()) -> List[SkillManifest]:
    """Load every skill folder. ``local_names`` are trusted as LOCAL."""
    manifests = []
    if not skills_dir.exists():
        return manifests
    for child in sorted(skills_dir.iterdir()):
        if not child.is_dir() or not (child / "SKILL.md").exists():
            continue
        if (child / ".disabled").exists():
            logger.info("skill %s disabled, skipping", child.name)
            continue
        trust = (TrustLevel.LOCAL if child.name in local_names
                 else TrustLevel.THIRD_PARTY)
        if trust is not TrustLevel.LOCAL:
            # Phase 9 moonshot: a marketplace-installed skill carries a
            # signed install record; re-verify its pins and honour the
            # recorded trust tier (fail-closed → THIRD_PARTY).
            try:
                from jarvis.marketplace.installer import trust_for_installed
                trust = trust_for_installed(child)
            except Exception:
                logger.exception("skill %s: trust check failed", child.name)
        try:
            manifests.append(load_skill(child, trust=trust))
        except Exception as e:
            logger.error("skill %s failed to load: %s", child.name, e)
    digest = sha256_of(skills_dir) if manifests else ""
    logger.info("loaded %d skills from %s (sha256 %.12s)",
                len(manifests), skills_dir, digest)
    return manifests
