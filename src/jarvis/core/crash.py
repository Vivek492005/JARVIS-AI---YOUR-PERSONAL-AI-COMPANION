"""Local crash reports (Task 8.3).

Every abnormal exit writes a JSON report under ``~/.jarvis/crashes/``.
Upload is **opt-in only** (``[privacy] crash_upload = true`` plus an
explicit endpoint); by default reports never leave the machine.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import traceback
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def crash_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), ".jarvis", "crashes")
    os.makedirs(d, exist_ok=True)
    return d


def write_crash_report(summary: str,
                       context: Optional[Dict[str, Any]] = None,
                       exc: Optional[BaseException] = None) -> str:
    """Write a crash report, return its path. Never raises."""
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        report = {
            "timestamp": ts,
            "summary": summary,
            "context": context or {},
            "traceback": "".join(traceback.format_exception(exc)) if exc else None,
        }
        path = os.path.join(crash_dir(), f"crash-{ts}.json")
        # Avoid clobbering if two crashes land in the same second.
        n = 1
        base = path
        while os.path.exists(path):
            path = base.replace(".json", f"-{n}.json")
            n += 1
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        logger.error("crash report written: %s (%s)", path, summary)
        _maybe_upload(report)
        return path
    except Exception as e:  # noqa: BLE001 — reporting must never crash the app
        logger.error("failed to write crash report: %s", e)
        return ""


def _maybe_upload(report: Dict[str, Any]) -> None:
    """Opt-in upload. Disabled unless the user explicitly enables it."""
    try:
        from jarvis.core.config import get_settings
        s = get_settings()
        if not s.privacy.crash_upload or not s.privacy.crash_upload_url:
            return
        url = s.privacy.crash_upload_url
        # Only https endpoints — never file:// or custom schemes.
        from urllib.parse import urlparse
        if urlparse(url).scheme != "https":
            logger.warning("crash upload URL must be https; skipping")
            return
        import urllib.request
        # NOTE: S310 suppressed below — the URL is user-configured (opt-in)
        # AND scheme-validated to https-only above this block.
        req = urllib.request.Request(  # noqa: S310 — user-configured https-only URL (validated above)
            url,
            data=json.dumps(report).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST")
        urllib.request.urlopen(req, timeout=10)  # noqa: S310
        logger.info("crash report uploaded (opt-in)")
    except Exception as e:  # noqa: BLE001 — upload failure is non-fatal
        logger.warning("crash upload failed: %s", e)
