"""Auto-update client (Task 8.4).

Checks GitHub Releases for a newer tag, downloads the installer asset, and
verifies its SHA256 against the published SHA256SUMS.txt before handing the
file to the user. Never auto-installs: the user always confirms, and the
hash check fails closed (mismatch = abort + warn).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.request
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

REPO_API = ("https://api.github.com/repos/Vivek492005/"
            "JARVIS-AI---YOUR-PERSONAL-AI-COMPANION/releases/latest")


@dataclass
class ReleaseInfo:
    tag: str
    installer_url: str
    sums_url: str


def _https_only(url: str) -> str:
    """Allow only https URLs (update assets come from GitHub)."""
    from urllib.parse import urlparse
    if urlparse(url).scheme != "https":
        raise ValueError(f"refusing non-https URL: {url!r}")
    return url


def _get_json(url: str) -> dict:
    req = urllib.request.Request(  # noqa: S310 — https-validated below
        _https_only(url), headers={"User-Agent": "jarvis-updater"})
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        return json.load(resp)


def check_for_update(current_version: str,
                     api_url: str = REPO_API) -> Optional[ReleaseInfo]:
    """Return ReleaseInfo if a newer release exists, else None.

    `current_version` like "0.9.0" (no leading v). Network failures return
    None (update check is best-effort, never fatal).
    """
    try:
        data = _get_json(api_url)
    except Exception as e:
        logger.warning("update check failed: %s", e)
        return None
    tag = str(data.get("tag_name", "")).lstrip("v")
    if not tag or tag == current_version:
        return None
    assets = {a.get("name", ""): a.get("browser_download_url", "")
              for a in data.get("assets", [])}
    installer = next((u for n, u in assets.items()
                      if n.startswith("JARVIS-Setup-v") and n.endswith(".exe")),
                     "")
    sums = assets.get("SHA256SUMS.txt", "")
    if not installer or not sums:
        logger.warning("release %s missing installer/checksums", tag)
        return None
    return ReleaseInfo(tag=tag, installer_url=installer, sums_url=sums)


def verify_sha256(file_path: str, sums_text: str) -> bool:
    """Check file_path against a SHA256SUMS.txt body. Fail-closed."""
    basename = os.path.basename(file_path)
    expected = None
    for line in sums_text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1] == basename:
            expected = parts[0]
            break
    if not expected:
        logger.error("no checksum entry for %s", basename)
        return False
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    ok = h.hexdigest().lower() == expected.lower()
    if not ok:
        logger.error("SHA256 MISMATCH for %s — aborting", basename)
    return ok


def download(url: str, dest: str) -> str:
    """Download url to dest. Returns dest."""
    req = urllib.request.Request(  # noqa: S310 — https-validated asset URL
        _https_only(url), headers={"User-Agent": "jarvis-updater"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
    return dest
