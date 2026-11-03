"""Skill package format (``.jskill``) — parse-only, never executes package code.

A package is a directory (or ``.jskill`` zip archive) with this layout::

    MANIFEST.json     # package metadata + sha256 pin for every file
    SIGNATURE.json    # Ed25519 signature over the canonical manifest bytes
    SKILL.md          # the existing skill manifest (name/version/permissions/tools)
    tool.py           # skill implementation (NOT imported during install/verify)
    ...               # any other files, all hash-pinned

Security posture: everything here parses data. ``tool.py`` is never
imported, ``SKILL.md`` is only frontmatter-parsed by the existing loader,
and any anomaly (unknown manifest field, hash mismatch, extra file,
bad signature) fails closed with :class:`PackageError`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

PACKAGE_FORMAT = "jarvis-skill-package/1"
MANIFEST_NAME = "MANIFEST.json"
SIGNATURE_NAME = "SIGNATURE.json"
PACKAGE_EXT = ".jskill"

# Conservative limits: packages are small text/code bundles.
_MAX_FILES = 500
_MAX_TOTAL_BYTES = 50 * 1024 * 1024
_MAX_SINGLE_BYTES = 10 * 1024 * 1024

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_KEY_ID_RE = re.compile(r"^[0-9a-f]{16}$")

_REQUIRED_MANIFEST_FIELDS = (
    "format", "name", "version", "author", "author_key_id",
    "min_jarvis", "permissions", "files",
)
_OPTIONAL_MANIFEST_FIELDS = ("description", "homepage", "created")


class PackageError(ValueError):
    """Any package anomaly — always fail closed."""


def canonical_bytes(obj) -> bytes:
    """Deterministic JSON encoding used for signing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_name(name: object) -> str:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise PackageError(f"bad skill name: {name!r}")
    return name


def _check_version(version: object) -> str:
    if not isinstance(version, str) or not _VERSION_RE.match(version):
        raise PackageError(f"bad version (want X.Y.Z): {version!r}")
    return version


def validate_manifest_schema(data: object) -> Dict:
    """Strict schema check. Raises PackageError on ANY anomaly."""
    if not isinstance(data, dict):
        raise PackageError("MANIFEST.json must be a JSON object")
    allowed = set(_REQUIRED_MANIFEST_FIELDS) | set(_OPTIONAL_MANIFEST_FIELDS)
    unknown = set(data) - allowed
    if unknown:
        raise PackageError(f"unknown manifest fields: {sorted(unknown)}")
    missing = [k for k in _REQUIRED_MANIFEST_FIELDS if k not in data]
    if missing:
        raise PackageError(f"missing manifest fields: {missing}")
    if data["format"] != PACKAGE_FORMAT:
        raise PackageError(f"unsupported package format: {data['format']!r}")
    _check_name(data["name"])
    _check_version(data["version"])
    _check_version(data["min_jarvis"])
    if not isinstance(data["author"], str) or not data["author"].strip():
        raise PackageError("author must be a non-empty string")
    if not isinstance(data["author_key_id"], str) or \
            not _KEY_ID_RE.match(data["author_key_id"]):
        raise PackageError("author_key_id must be 16 hex chars")
    if not isinstance(data["permissions"], list) or not all(
            isinstance(p, str) and p.strip() for p in data["permissions"]):
        raise PackageError("permissions must be a list of strings")
    if len(set(data["permissions"])) != len(data["permissions"]):
        raise PackageError("duplicate permissions")
    files = data["files"]
    if not isinstance(files, dict) or not files:
        raise PackageError("files must be a non-empty {path: sha256} map")
    for rel, digest in files.items():
        if not isinstance(rel, str) or not isinstance(digest, str):
            raise PackageError(f"bad files entry: {rel!r}")
        if rel.startswith("/") or ".." in Path(rel).parts or not rel.strip():
            raise PackageError(f"unsafe file path in manifest: {rel!r}")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise PackageError(f"bad sha256 for {rel!r}")
        if rel in (MANIFEST_NAME, SIGNATURE_NAME):
            raise PackageError(f"{rel!r} must not be hash-pinned")
    for opt in _OPTIONAL_MANIFEST_FIELDS:
        if opt in data and not isinstance(data[opt], str):
            raise PackageError(f"{opt} must be a string")
    return data


def _check_zip_member(zinfo: zipfile.ZipInfo) -> str:
    name = zinfo.filename
    if name.startswith("/") or ".." in Path(name).parts:
        raise PackageError(f"unsafe zip member: {name!r}")
    if zinfo.is_dir():
        raise PackageError(f"unexpected directory in package: {name!r}")
    # Refuse symlinks (Unix external_attr >> 16 holds the file type).
    if (zinfo.external_attr >> 28) == 0xA:
        raise PackageError(f"symlink refused in package: {name!r}")
    if zinfo.file_size > _MAX_SINGLE_BYTES:
        raise PackageError(f"package member too large: {name!r}")
    return name


@dataclass
class LoadedPackage:
    """A package extracted to a temp dir (parse-only)."""
    root: Path
    manifest: Dict
    signature: Dict
    _tmpdir: Optional[tempfile.TemporaryDirectory] = field(default=None,
                                                           repr=False)

    def close(self) -> None:
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None


def _read_json(path: Path, what: str) -> Dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise PackageError(f"cannot read {what}: {e}") from e
    if not isinstance(data, dict):
        raise PackageError(f"{what} must be a JSON object")
    return data


def load_package(path: str | Path,
                 require_signature: bool = True) -> LoadedPackage:
    """Load a package dir or .jskill zip. Raises PackageError on anomaly."""
    src = Path(path)
    if not src.exists():
        raise PackageError(f"package not found: {src}")
    if src.is_file():
        if src.suffix != PACKAGE_EXT:
            raise PackageError(f"not a {PACKAGE_EXT} file: {src}")
        tmp = tempfile.TemporaryDirectory(prefix="jskill_")
        root = Path(tmp.name)
        total = 0
        count = 0
        with zipfile.ZipFile(src, "r") as zf:
            members = zf.infolist()
            for info in members:
                _check_zip_member(info)
                count += 1
                total += info.file_size
            if count == 0 or count > _MAX_FILES:
                raise PackageError(f"bad member count: {count}")
            if total > _MAX_TOTAL_BYTES:
                raise PackageError("package too large")
            for info in members:
                target = root / info.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as fin, open(target, "wb") as fout:
                    shutil.copyfileobj(fin, fout)
        keep_tmp: Optional[tempfile.TemporaryDirectory] = tmp
    elif src.is_dir():
        root = src
        keep_tmp = None
    else:
        raise PackageError(f"not a package: {src}")

    try:
        manifest_raw = _read_json(root / MANIFEST_NAME, MANIFEST_NAME)
        manifest = validate_manifest_schema(manifest_raw)
        if require_signature:
            signature = _read_json(root / SIGNATURE_NAME, SIGNATURE_NAME)
        else:
            try:
                signature = _read_json(root / SIGNATURE_NAME, SIGNATURE_NAME)
            except PackageError:
                signature = {}
    except PackageError:
        if keep_tmp is not None:
            keep_tmp.cleanup()
        raise
    return LoadedPackage(root=root, manifest=manifest, signature=signature,
                         _tmpdir=keep_tmp)


def build_package(skill_dir: str | Path, *, author: str,
                  author_key_id: str, min_jarvis: str,
                  version: Optional[str] = None,
                  out_dir: Optional[Path] = None) -> Path:
    """Author flow: build an UNSIGNED package dir from a skill folder.

    Reads SKILL.md via the existing loader (frontmatter only — tool.py is
    never imported). Returns the staging directory; call
    :func:`jarvis.marketplace.signing.sign_package` next.
    """
    from jarvis.brain.skills.loader import load_manifest  # lazy: brain deps

    src = Path(skill_dir)
    if not src.is_dir() or not (src / "SKILL.md").exists():
        raise PackageError(f"not a skill dir: {src}")
    manifest = load_manifest(src)
    name = _check_name(manifest.name)
    ver = _check_version(version or manifest.version)
    _check_version(min_jarvis)
    if not isinstance(author, str) or not author.strip():
        raise PackageError("author must be a non-empty string")
    if not _KEY_ID_RE.match(author_key_id or ""):
        raise PackageError("author_key_id must be 16 hex chars")

    staging = Path(out_dir) if out_dir else Path(
        tempfile.mkdtemp(prefix=f"{name}-{ver}_"))
    staging.mkdir(parents=True, exist_ok=True)

    files: Dict[str, str] = {}
    for child in sorted(src.rglob("*")):
        if not child.is_file():
            continue
        rel = child.relative_to(src).as_posix()
        if rel.startswith(".") and "/" not in rel:
            continue  # skip dotfiles like .disabled
        if child.stat().st_size > _MAX_SINGLE_BYTES:
            raise PackageError(f"file too large to package: {rel!r}")
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(child, dest)
        files[rel] = sha256_file(dest)
    if not files or "SKILL.md" not in files:
        raise PackageError("skill dir has no SKILL.md to package")

    pkg_manifest = {
        "format": PACKAGE_FORMAT,
        "name": name,
        "version": ver,
        "author": author.strip(),
        "author_key_id": author_key_id,
        "min_jarvis": min_jarvis,
        "permissions": sorted(set(manifest.permissions)),
        "files": files,
        "description": manifest.description,
    }
    validate_manifest_schema(pkg_manifest)  # fail fast
    (staging / MANIFEST_NAME).write_text(
        json.dumps(pkg_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    logger.info("built unsigned package %s v%s (%d files) at %s",
                name, ver, len(files), staging)
    return staging


def pack_zip(package_dir: Path, dest: Optional[Path] = None) -> Path:
    """Zip a signed package dir into ``<name>-<version>.jskill``."""
    package_dir = Path(package_dir)
    if not (package_dir / SIGNATURE_NAME).exists():
        raise PackageError("refusing to ship an unsigned package")
    pkg = load_package(package_dir)  # validates schema
    try:
        name, ver = pkg.manifest["name"], pkg.manifest["version"]
    finally:
        pkg.close()
    dest = dest or Path(f"{name}-{ver}{PACKAGE_EXT}")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for child in sorted(package_dir.rglob("*")):
            if child.is_file():
                zf.write(child, child.relative_to(package_dir).as_posix())
    return dest


def list_package_files(root: Path) -> List[str]:
    """Relative posix paths of all files under root (excluding dotfiles)."""
    out = []
    for child in sorted(root.rglob("*")):
        if child.is_file():
            rel = child.relative_to(root).as_posix()
            if rel.startswith(".") and "/" not in rel:
                continue
            out.append(rel)
    return out
