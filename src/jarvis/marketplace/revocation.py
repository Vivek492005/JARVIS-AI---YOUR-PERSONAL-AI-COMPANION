"""Revocation: local cache + signed feed format (offline-safe).

* Local cache ``~/.jarvis/marketplace/revoked.json`` is consulted on every
  install/verify — no network needed.
* Curators publish a signed JSON feed; ``update_from_feed`` verifies the
  curator signature before merging, so a tampered feed is ignored.
* Feed format version ``jarvis-revocation-feed/1``; the signature covers
  the canonical bytes of the feed body (everything except ``signature``).

Out of scope: the actual registry server / feed hosting (see
docs/SKILL_MARKETPLACE.md).
"""

from __future__ import annotations

import datetime
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from jarvis.marketplace import ed25519
from jarvis.marketplace.package import PackageError, canonical_bytes
from jarvis.marketplace.signing import marketplace_dir

logger = logging.getLogger(__name__)

FEED_FORMAT = "jarvis-revocation-feed/1"
_CACHE_NAME = "revoked.json"


@dataclass
class RevocationList:
    revoked_keys: List[str] = field(default_factory=list)
    revoked_packages: List[str] = field(default_factory=list)  # "name@version"
    updated_at: str = ""

    def is_revoked(self, key_id: str, name: str, version: str) -> Optional[str]:
        if key_id in self.revoked_keys:
            return f"signing key {key_id} is revoked"
        if f"{name}@{version}" in self.revoked_packages:
            return f"package {name}@{version} is revoked"
        return None


def _cache_path() -> Path:
    return marketplace_dir() / _CACHE_NAME


def load_local() -> RevocationList:
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return RevocationList()
    keys = data.get("revoked_keys", [])
    pkgs = data.get("revoked_packages", [])
    if not isinstance(keys, list) or not isinstance(pkgs, list):
        logger.warning("revocation cache corrupt; ignoring")
        return RevocationList()
    return RevocationList(
        revoked_keys=[str(k) for k in keys],
        revoked_packages=[str(p) for p in pkgs],
        updated_at=str(data.get("updated_at", "")))


def save_local(rev: RevocationList) -> None:
    _cache_path().write_text(json.dumps({
        "revoked_keys": sorted(set(rev.revoked_keys)),
        "revoked_packages": sorted(set(rev.revoked_packages)),
        "updated_at": rev.updated_at or datetime.datetime.now().isoformat(
            timespec="seconds"),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check_revoked(key_id: str, name: str, version: str) -> Optional[str]:
    """Hook for verify_package(): None = clean, str = refusal reason."""
    return load_local().is_revoked(key_id, name, version)


def verify_feed(feed: Dict, curator_public_key_hex: str) -> RevocationList:
    """Verify a signed feed dict. Raises PackageError on any anomaly."""
    if not isinstance(feed, dict):
        raise PackageError("feed must be a JSON object")
    if feed.get("format") != FEED_FORMAT:
        raise PackageError(
            f"unsupported feed format: {feed.get('format')!r}")
    sig = feed.get("signature")
    if not isinstance(sig, dict) or sig.get("algorithm") != "ed25519":
        raise PackageError("feed has no valid signature block")
    try:
        pub = bytes.fromhex(curator_public_key_hex.strip())
        s = bytes.fromhex(sig["signature"])
    except ValueError as e:
        raise PackageError(f"bad hex in feed signature: {e}") from e
    if len(pub) != 32 or len(s) != 64:
        raise PackageError("bad feed signature lengths")
    if ed25519.key_id(pub) != sig.get("key_id"):
        raise PackageError("feed key_id does not match curator key")
    body = {k: v for k, v in feed.items() if k != "signature"}
    if not ed25519.verify(pub, canonical_bytes(body), s):
        raise PackageError("feed signature verification FAILED")
    keys = body.get("revoked_keys", [])
    pkgs = body.get("revoked_packages", [])
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise PackageError("bad revoked_keys in feed")
    if not isinstance(pkgs, list) or not all(isinstance(p, str) for p in pkgs):
        raise PackageError("bad revoked_packages in feed")
    return RevocationList(revoked_keys=list(keys), revoked_packages=list(pkgs),
                          updated_at=str(body.get("issued_at", "")))


def update_from_feed(feed_path: str | Path,
                     curator_public_key_hex: str) -> RevocationList:
    """Verify ``feed_path`` and merge it into the local cache."""
    try:
        feed = json.loads(Path(feed_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise PackageError(f"cannot read feed: {e}") from e
    incoming = verify_feed(feed, curator_public_key_hex)
    current = load_local()
    merged = RevocationList(
        revoked_keys=sorted(set(current.revoked_keys) | set(incoming.revoked_keys)),
        revoked_packages=sorted(set(current.revoked_packages) | set(incoming.revoked_packages)),
        updated_at=incoming.updated_at or current.updated_at,
    )
    save_local(merged)
    logger.info("revocation cache updated: %d keys, %d packages",
                len(merged.revoked_keys), len(merged.revoked_packages))
    return merged


def sign_feed(revoked_keys: List[str], revoked_packages: List[str],
              secret_seed: bytes) -> Dict:
    """Curator-side helper: build a signed feed dict."""
    if len(secret_seed) != 32:
        raise PackageError("secret seed must be 32 bytes")
    pub = ed25519.keypair(bytes(secret_seed))[1]
    body = {
        "format": FEED_FORMAT,
        "issued_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "revoked_keys": sorted(set(revoked_keys)),
        "revoked_packages": sorted(set(revoked_packages)),
    }
    sig = ed25519.sign(bytes(secret_seed), canonical_bytes(body))
    return {**body, "signature": {
        "algorithm": "ed25519",
        "key_id": ed25519.key_id(pub),
        "public_key": pub.hex(),
        "signature": sig.hex(),
    }}
