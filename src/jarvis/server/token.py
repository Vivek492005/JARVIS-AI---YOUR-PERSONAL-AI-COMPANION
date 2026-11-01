"""Per-install bearer <redacted> for jarvisd (Master Plan Task 2.4).

The token lives at ``%APPDATA%\\\\jarvis\\\\token`` on Windows and
``~/.jarvis/token`` elsewhere, created once with 0600 permissions.
It is never logged — see Task 1.9 secret redaction.
"""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

logger = logging.getLogger(__name__)

TOKEN_BYTES = 32


def token_path() -> Path:
    appdata = os.getenv("APPDATA")
    if os.name == "nt" and appdata:
        base = Path(appdata) / "jarvis"
    else:
        base = Path.home() / ".jarvis"
    return base / "token"


def get_or_create_token(path: Path | None = None) -> str:
    """Return the install token, creating and persisting it on first use."""
    p = path or token_path()
    if p.exists():
        token = p.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_hex(TOKEN_BYTES)
    p.parent.mkdir(parents=True, exist_ok=True)
    # 0600: only the owner can read it.
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token + "\n")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    logger.info("created new jarvisd bearer <redacted> at %s", p)
    return token


def bearer_ok(header_value: str | None, token: str) -> bool:
    """Constant-time check of an ``Authorization: Bearer ...`` header."""
    if not header_value:
        return False
    scheme, _, presented = header_value.partition(" ")
    if scheme.lower() != "bearer" or not presented:
        return False
    return secrets.compare_digest(presented.strip(), token)
