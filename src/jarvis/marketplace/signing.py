"""Skill signing: Ed25519 sign/verify + trust tiers.

Trust model (see docs/SKILL_MARKETPLACE.md for the full story):

* ``unsigned``   — no SIGNATURE.json, or structurally invalid. REFUSED.
* ``self-signed``— signature valid, key unknown. Installable only with
  explicit user confirmation; tools stay at the DESTRUCTIVE floor;
  sandbox Level B+ required.
* ``curator``    — signature valid AND key in the local curator store.
  Installable with explicit confirmation; the manifest-declared risk
  tiers are honoured (the install prompt lists every tool + risk).
* ``verified``   — reserved for keys endorsed by the JARVIS project
  itself. Key ceremony is out of scope; treated like ``curator``.

A signature binds: author_key_id == key_id(public_key), and the
signature covers the canonical MANIFEST.json bytes. File integrity is
covered separately by the hash pins in the manifest.
"""

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from jarvis.marketplace import ed25519
from jarvis.marketplace.package import (
    MANIFEST_NAME, SIGNATURE_NAME, PackageError,
    canonical_bytes, list_package_files, load_package, sha256_file,
)

logger = logging.getLogger(__name__)

TRUST_SELF_SIGNED = "self-signed"
TRUST_CURATOR = "curator"
TRUST_VERIFIED = "verified"  # reserved: project-endorsed keys


def marketplace_dir() -> Path:
    d = Path.home() / ".jarvis" / "marketplace"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Curator key store (public keys only — never secrets)
# ---------------------------------------------------------------------------

@dataclass
class CuratorKey:
    key_id: str
    public_key: str  # hex, 32 bytes
    name: str = ""
    added_at: str = ""


class CuratorStore:
    """Local trust anchors: {key_id: CuratorKey}, JSON on disk."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or (marketplace_dir() / "curators.json")
        self._keys: Dict[str, CuratorKey] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for entry in data.get("keys", []):
            try:
                kid = entry["key_id"]
                pub = bytes.fromhex(entry["public_key"])
                if len(pub) != 32 or ed25519.key_id(pub) != kid:
                    logger.warning("curator store: key_id mismatch, skipping")
                    continue
                self._keys[kid] = CuratorKey(
                    key_id=kid, public_key=entry["public_key"],
                    name=str(entry.get("name", "")),
                    added_at=str(entry.get("added_at", "")))
            except (KeyError, ValueError, TypeError) as e:
                logger.warning("curator store: bad entry skipped: %s", e)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"keys": [
            {"key_id": k.key_id, "public_key": k.public_key,
             "name": k.name, "added_at": k.added_at}
            for k in sorted(self._keys.values(), key=lambda k: k.key_id)]}
        self.path.write_text(json.dumps(data, indent=2) + "\n",
                             encoding="utf-8")

    def add(self, public_key_hex: str, name: str = "") -> CuratorKey:
        try:
            pub = bytes.fromhex(public_key_hex.strip())
        except ValueError as e:
            raise PackageError(f"bad public key hex: {e}") from e
        if len(pub) != 32:
            raise PackageError("public key must be 32 bytes (64 hex chars)")
        key = CuratorKey(key_id=ed25519.key_id(pub),
                         public_key=pub.hex(), name=name,
                         added_at=datetime.datetime.now().isoformat(
                             timespec="seconds"))
        self._keys[key.key_id] = key
        self._save()
        logger.info("curator key added: %s (%s)", key.key_id, name)
        return key

    def remove(self, key_id: str) -> bool:
        if key_id in self._keys:
            del self._keys[key_id]
            self._save()
            return True
        return False

    def list(self) -> List[CuratorKey]:
        return sorted(self._keys.values(), key=lambda k: k.key_id)

    def is_curator(self, key_id: str) -> bool:
        return key_id in self._keys


# ---------------------------------------------------------------------------
# Signing (author side)
# ---------------------------------------------------------------------------

def sign_package(package_dir: str | Path, secret_seed: bytes) -> Dict:
    """Sign a package dir built by build_package(). Writes SIGNATURE.json.

    ``secret_seed`` is the author's 32-byte Ed25519 seed — never logged,
    never written to disk by this function.
    """
    root = Path(package_dir)
    pkg = load_package(root, require_signature=False)
    try:
        manifest = pkg.manifest
    finally:
        pkg.close()
    if pkg.signature:
        raise PackageError("package is already signed")
    if len(secret_seed) != 32:
        raise PackageError("secret seed must be 32 bytes")
    public_key = ed25519.keypair(bytes(secret_seed))[1]
    key_id = ed25519.key_id(public_key)
    if key_id != manifest["author_key_id"]:
        raise PackageError(
            f"signing key {key_id} does not match manifest "
            f"author_key_id {manifest['author_key_id']!r}")
    signature = ed25519.sign(bytes(secret_seed), canonical_bytes(manifest))
    sig_doc = {
        "algorithm": "ed25519",
        "key_id": key_id,
        "public_key": public_key.hex(),
        "signature": signature.hex(),
        "signed_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    (root / SIGNATURE_NAME).write_text(
        json.dumps(sig_doc, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    logger.info("signed package %s v%s with key %s",
                manifest["name"], manifest["version"], key_id)
    return sig_doc


# ---------------------------------------------------------------------------
# Verification (install/verify side)
# ---------------------------------------------------------------------------

@dataclass
class VerificationResult:
    ok: bool
    trust: str = ""            # self-signed | curator | verified
    key_id: str = ""
    name: str = ""
    version: str = ""
    author: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _verify_signature_structure(sig: Dict) -> None:
    if sig.get("algorithm") != "ed25519":
        raise PackageError(
            f"unsupported signature algorithm: {sig.get('algorithm')!r}")
    for f_ in ("key_id", "public_key", "signature"):
        if f_ not in sig:
            raise PackageError(f"SIGNATURE.json missing field: {f_}")
    try:
        pub = bytes.fromhex(sig["public_key"])
        s = bytes.fromhex(sig["signature"])
    except ValueError as e:
        raise PackageError(f"bad hex in SIGNATURE.json: {e}") from e
    if len(pub) != 32:
        raise PackageError("public_key must be 32 bytes")
    if len(s) != 64:
        raise PackageError("signature must be 64 bytes")
    if ed25519.key_id(pub) != sig["key_id"]:
        raise PackageError("key_id does not match public_key")


def verify_signature(pkg_root: Path, manifest: Dict,
                     sig: Dict) -> tuple[str, str]:
    """Returns (key_id, trust_tier). Raises PackageError on any failure."""
    _verify_signature_structure(sig)
    pub = bytes.fromhex(sig["public_key"])
    if sig["key_id"] != manifest["author_key_id"]:
        raise PackageError("SIGNATURE key_id != MANIFEST author_key_id")
    if not ed25519.verify(pub, canonical_bytes(manifest),
                           bytes.fromhex(sig["signature"])):
        raise PackageError("signature verification FAILED")
    return sig["key_id"], TRUST_SELF_SIGNED  # tier upgraded by caller


def verify_file_hashes(pkg_root: Path, manifest: Dict) -> List[str]:
    """Check every pinned hash; also refuse unpinned extra files."""
    errors: List[str] = []
    pinned = manifest["files"]
    for rel, want in pinned.items():
        target = pkg_root / rel
        if not target.is_file():
            errors.append(f"pinned file missing: {rel}")
            continue
        got = sha256_file(target)
        if got != want:
            errors.append(f"hash mismatch: {rel}")
    actual = set(list_package_files(pkg_root))
    expected = set(pinned) | {MANIFEST_NAME, SIGNATURE_NAME}
    for extra in sorted(actual - expected):
        errors.append(f"unpinned file refused: {extra}")
    return errors


def verify_package(path: str | Path,
                   curators: Optional[CuratorStore] = None,
                   check_revocation=None) -> VerificationResult:
    """Full offline verification. Never imports package code."""
    res = VerificationResult(ok=False)
    try:
        pkg = load_package(path)
    except PackageError as e:
        res.errors.append(str(e))
        return res
    try:
        manifest, sig = pkg.manifest, pkg.signature
        res.name = manifest["name"]
        res.version = manifest["version"]
        res.author = manifest["author"]
        try:
            key_id, _tier = verify_signature(pkg.root, manifest, sig)
        except PackageError as e:
            res.errors.append(str(e))
            return res
        res.key_id = key_id
        store = curators or CuratorStore()
        res.trust = (TRUST_CURATOR if store.is_curator(key_id)
                     else TRUST_SELF_SIGNED)
        hash_errors = verify_file_hashes(pkg.root, manifest)
        if hash_errors:
            res.errors.extend(hash_errors)
            return res
        # SKILL.md must agree with the package manifest (parse-only).
        try:
            from jarvis.brain.skills.loader import load_manifest
            skill_manifest = load_manifest(pkg.root)
        except Exception as e:
            res.errors.append(f"SKILL.md invalid: {e}")
            return res
        if skill_manifest.name != manifest["name"]:
            res.errors.append("SKILL.md name != MANIFEST name")
            return res
        if skill_manifest.version != manifest["version"]:
            res.errors.append("SKILL.md version != MANIFEST version")
            return res
        if sorted(set(skill_manifest.permissions)) != \
                sorted(set(manifest["permissions"])):
            res.errors.append(
                "SKILL.md permissions != MANIFEST permissions "
                "(declare them up front)")
            return res
        if check_revocation is not None:
            rev_err = check_revocation(key_id, manifest["name"],
                                       manifest["version"])
            if rev_err:
                res.errors.append(rev_err)
                return res
        res.ok = True
        return res
    finally:
        pkg.close()


def trust_to_skill_trust(trust: str):
    """Map marketplace trust tier -> brain TrustLevel."""
    from jarvis.brain.skills.trust import TrustLevel
    if trust in (TRUST_CURATOR, TRUST_VERIFIED):
        return TrustLevel.VERIFIED
    return TrustLevel.THIRD_PARTY
