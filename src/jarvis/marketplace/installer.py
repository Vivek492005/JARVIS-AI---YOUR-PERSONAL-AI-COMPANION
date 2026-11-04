"""Marketplace install flow — fail-closed at every step.

Order of checks (a malicious package must never execute code):

1. :func:`verify_package` — schema, signature, hash pins, SKILL.md
   agreement, revocation. Parse-only; ``tool.py`` is never imported.
2. ``min_jarvis`` compatibility.
3. Name collision (refuse; upgrades are explicit).
4. Sandbox gate: non-local trust needs Level B+ (``assert_skill_allowed``).
5. User-facing summary + explicit interactive confirmation. Non-tty or
   empty answer = refuse.
6. Copy the tree into the skills dir, write ``.marketplace.json``
   (trust record + file pins for load-time re-verification), update the
   installed registry, audit-log the decision.
"""

from __future__ import annotations

import datetime
import json
import logging
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from jarvis.marketplace.package import (
    PackageError,
    list_package_files,
    load_package,
)
from jarvis.marketplace.revocation import check_revoked
from jarvis.marketplace.signing import (
    TRUST_SELF_SIGNED,
    CuratorStore,
    marketplace_dir,
    trust_to_skill_trust,
    verify_package,
)

logger = logging.getLogger(__name__)

INSTALLED_RECORD = ".marketplace.json"
INSTALL_FORMAT = "jarvis-installed-skill/1"


@dataclass
class InstallResult:
    ok: bool
    name: str = ""
    version: str = ""
    trust: str = ""
    dest: Optional[Path] = None
    errors: List[str] = field(default_factory=list)


def _jarvis_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    for dist in ("jarvis-assistant", "jarvis-ai"):
        try:
            return version(dist)
        except PackageNotFoundError:
            continue
    logger.warning("could not determine JARVIS version; using 0.0.0")
    return "0.0.0"


def _version_tuple(v: str) -> tuple:
    return tuple(int(x) for x in v.split(".")[:3])


def _check_min_jarvis(min_jarvis: str) -> Optional[str]:
    try:
        if _version_tuple(_jarvis_version()) < _version_tuple(min_jarvis):
            return f"package needs JARVIS >= {min_jarvis} (running {_jarvis_version()})"
    except Exception:
        return f"cannot compare versions (min_jarvis={min_jarvis!r})"
    return None


def _audit(tool: str, args: Dict, decision: str, reason: str = "") -> None:
    try:
        from jarvis.policy.audit import AuditLogger

        AuditLogger().log(tool, args, decision, reason)
    except Exception:
        logger.exception("marketplace audit write failed")


def installed_registry_path() -> Path:
    return marketplace_dir() / "installed.json"


def _read_registry() -> Dict:
    try:
        data = json.loads(installed_registry_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_registry(reg: Dict) -> None:
    p = installed_registry_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def summarize_for_confirm(pkg_root: Path, manifest: Dict, trust: str) -> str:
    """Human-readable install summary shown before confirmation."""
    from jarvis.brain.skills.loader import load_manifest

    skill = load_manifest(pkg_root)
    lines = [
        f"Skill:   {manifest['name']} v{manifest['version']}",
        f"Author:  {manifest['author']}  (key {manifest['author_key_id']})",
        f"Trust:   {trust}",
        f"Files:   {len(manifest['files'])} pinned, signature OK",
        f"Permissions: {', '.join(manifest['permissions']) or '(none)'}",
        "Tools:",
    ]
    for t in skill.tools:
        lines.append(f"  - {t.name}  [risk: {t.risk}]")
    if trust == TRUST_SELF_SIGNED:
        lines.append(
            "NOTE: self-signed — all tools run at DESTRUCTIVE risk, sandbox Level B+ required."
        )
    return "\n".join(lines)


def default_confirm(prompt_text: str) -> bool:
    """Interactive confirmation. Fail-closed outside a tty."""
    if not sys.stdin.isatty():
        print("refusing: install needs an interactive confirmation", file=sys.stderr)
        return False
    print(prompt_text)
    answer = input("Install this skill? (haan/nahi): ").strip().lower()
    return answer in ("haan", "ha", "yes", "y")


def install_package(
    path: str | Path,
    skills_dir: Path,
    confirm: Callable[[str], bool] = default_confirm,
    curators: Optional[CuratorStore] = None,
) -> InstallResult:
    """Run the full install flow. Returns InstallResult (never raises)."""
    res = InstallResult(ok=False)
    audit_args: Dict = {"package": str(path)}
    try:
        result = verify_package(path, curators=curators, check_revocation=check_revoked)
    except Exception as e:  # fail-closed on unexpected errors
        res.errors.append(f"verification crashed: {e}")
        _audit("skill.install", audit_args, "deny", res.errors[0])
        return res
    audit_args.update(
        name=result.name, version=result.version, key_id=result.key_id, trust=result.trust
    )
    if not result.ok:
        res.errors.extend(result.errors)
        _audit("skill.install", audit_args, "deny", "; ".join(result.errors)[:300])
        return res

    # Re-open the package to copy files (verify_package closes its handle).
    try:
        pkg = load_package(path)
    except PackageError as e:
        res.errors.append(str(e))
        _audit("skill.install", audit_args, "deny", str(e))
        return res
    try:
        manifest = pkg.manifest
        res.name, res.version, res.trust = (result.name, result.version, result.trust)
        problem = _check_min_jarvis(manifest["min_jarvis"])
        if problem:
            res.errors.append(problem)
            _audit("skill.install", audit_args, "deny", problem)
            return res

        dest = Path(skills_dir) / manifest["name"]
        if dest.exists():
            msg = f"'{manifest['name']}' is already installed (uninstall it first to upgrade)"
            res.errors.append(msg)
            _audit("skill.install", audit_args, "deny", msg)
            return res

        # Sandbox gate: anything not LOCAL needs Level B+.
        skill_trust = trust_to_skill_trust(result.trust)
        try:
            from jarvis.perception.sandbox import assert_skill_allowed

            assert_skill_allowed(manifest["name"], skill_trust.value)
        except PermissionError as e:
            res.errors.append(str(e))
            _audit("skill.install", audit_args, "deny", str(e))
            return res
        except ImportError as e:
            msg = f"sandbox check unavailable: {e}"
            res.errors.append(msg)
            _audit("skill.install", audit_args, "deny", msg)
            return res

        summary = summarize_for_confirm(pkg.root, manifest, result.trust)
        if not confirm(summary):
            msg = "user did not confirm install"
            res.errors.append(msg)
            _audit("skill.install", audit_args, "deny", msg)
            return res

        # Copy the tree (data only — nothing is imported or executed).
        dest.mkdir(parents=True)
        for rel in list_package_files(pkg.root):
            src_file = pkg.root / rel
            dst_file = dest / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)

        record = {
            "format": INSTALL_FORMAT,
            "name": manifest["name"],
            "version": manifest["version"],
            "key_id": result.key_id,
            "trust": result.trust,
            "files": dict(manifest["files"]),
            "installed_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        (dest / INSTALLED_RECORD).write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        reg = _read_registry()
        reg[manifest["name"]] = {
            "version": manifest["version"],
            "key_id": result.key_id,
            "trust": result.trust,
            "installed_at": record["installed_at"],
        }
        _write_registry(reg)

        res.ok = True
        res.dest = dest
        _audit(
            "skill.install",
            audit_args,
            "allow",
            f"installed {manifest['name']} v{manifest['version']} trust={result.trust}",
        )
        logger.info(
            "installed skill %s v%s (trust=%s)", manifest["name"], manifest["version"], result.trust
        )
        return res
    finally:
        pkg.close()


def read_installed_record(skill_dir: Path) -> Optional[Dict]:
    """Read .marketplace.json; None if absent or corrupt."""
    p = Path(skill_dir) / INSTALLED_RECORD
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("format") != INSTALL_FORMAT:
        return None
    return data


def trust_for_installed(skill_dir: Path):
    """Re-verify install pins; return the skill TrustLevel (fail-closed).

    A valid, unmodified install record yields THIRD_PARTY (self-signed)
    or VERIFIED (curator). Anything else → THIRD_PARTY + warning.
    """
    from jarvis.brain.skills.trust import TrustLevel
    from jarvis.marketplace.package import sha256_file

    record = read_installed_record(skill_dir)
    if record is None:
        return TrustLevel.THIRD_PARTY
    try:
        for rel, want in record["files"].items():
            target = Path(skill_dir) / rel
            if not target.is_file() or sha256_file(target) != want:
                logger.warning(
                    "marketplace: %s modified after install; downgrading trust", record.get("name")
                )
                return TrustLevel.THIRD_PARTY
        trust = record.get("trust", TRUST_SELF_SIGNED)
        return trust_to_skill_trust(trust)
    except Exception:
        logger.exception("marketplace: bad install record")
        return TrustLevel.THIRD_PARTY
