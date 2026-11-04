"""Task 1.9: secrets handling.

Priority for every secret: explicit env var > OS keyring > .env file.
The keyring is optional — when unavailable, .env remains the fallback and
every function degrades gracefully instead of crashing.

Also here: SecretRedactingFilter, a logging filter that scrubs known
secret *values* out of log records, so a stray f-string can never leak a
key into the logs (defense in depth next to the audit redaction in 1.7).
"""

from __future__ import annotations

import getpass
import logging
import os
import sys
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "jarvis-assistant"

# Env var -> keyring account name.
SECRET_NAMES: Dict[str, str] = {
    "HUGGINGFACE_API_KEY": "huggingface_api_key",
    "DEEPSEEK_API_KEY": "deepseek_api_key",
    "RUMIK_API_KEY": "rumik_api_key",
}


def keyring_available() -> bool:
    try:
        import keyring  # type: ignore

        # A backend that can actually store (not the fail backend).
        return not str(type(keyring.get_keyring())).endswith("FailKeyring'>")
    except ImportError:
        return False
    except Exception:
        return False


def get_secret(env_name: str) -> str:
    """Read a secret: env var first, then OS keyring, else ''.

    Never raises for a missing keyring — returns '' so callers keep their
    existing 'no key configured' behavior.
    """
    value = os.getenv(env_name, "")
    if value:
        return value
    if not keyring_available():
        return ""
    try:
        import keyring  # type: ignore

        return keyring.get_password(KEYRING_SERVICE, SECRET_NAMES.get(env_name, env_name)) or ""
    except Exception as e:
        logger.warning(f"keyring read failed for {env_name}: {e}")
        return ""


def store_secret(env_name: str, value: str) -> bool:
    """Store a secret in the OS keyring. False when unavailable."""
    if not keyring_available():
        logger.warning("keyring unavailable — put the key in .env instead")
        return False
    try:
        import keyring  # type: ignore

        keyring.set_password(KEYRING_SERVICE, SECRET_NAMES.get(env_name, env_name), value)
        return True
    except Exception as e:
        logger.error(f"keyring store failed for {env_name}: {e}")
        return False


def delete_secret(env_name: str) -> bool:
    if not keyring_available():
        return False
    try:
        import keyring  # type: ignore

        keyring.delete_password(KEYRING_SERVICE, SECRET_NAMES.get(env_name, env_name))
        return True
    except Exception:
        logger.debug(f"keyring delete failed for {env_name} (non-fatal)")
        return False


def secret_status() -> Dict[str, Dict[str, bool]]:
    """Where each secret is configured — values never included."""
    out = {}
    for env_name in SECRET_NAMES:
        out[env_name] = {
            "env": bool(os.getenv(env_name)),
            "keyring": bool(
                keyring_available() and get_secret(env_name) and not os.getenv(env_name)
            ),
        }
    return out


# ---------------------------------------------------------------------------
# Logging redaction filter
# ---------------------------------------------------------------------------


class SecretRedactingFilter(logging.Filter):
    """Scrub registered secret values out of log records."""

    def __init__(self):
        super().__init__()
        self._values: List[str] = []

    def add_secret(self, value: Optional[str]) -> None:
        if value and len(value) >= 8 and value not in self._values:
            self._values.append(value)

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            for v in self._values:
                if v in msg:
                    msg = msg.replace(v, "***REDACTED***")
            # Rebuild the record so the redacted text is what gets emitted.
            record.msg = msg
            record.args = ()
        except Exception:  # noqa: S110 — a logging filter must never raise;
            # nothing is safe to log from inside the logging pipeline itself.
            pass
        return True


_redacting_filter: Optional[SecretRedactingFilter] = None


def install_secret_redaction() -> SecretRedactingFilter:
    """Register every configured secret value for log scrubbing.

    Idempotent. Call once at startup (main.py does this).
    """
    global _redacting_filter
    if _redacting_filter is None:
        _redacting_filter = SecretRedactingFilter()
        for env_name in SECRET_NAMES:
            _redacting_filter.add_secret(get_secret(env_name))
        logging.getLogger().addFilter(_redacting_filter)
        # Also cover the JARVIS loggers that may have their own handlers.
        for name in ("access_os", "main"):
            logging.getLogger(name).addFilter(_redacting_filter)
    return _redacting_filter


# ---------------------------------------------------------------------------
# CLI: python -m access_os.secrets <store|delete|status>
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="jarvis secrets", description="Manage secrets (OS keyring)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("store", help="store a key in the OS keyring")
    p.add_argument("name", choices=list(SECRET_NAMES), help="which secret to store")

    p = sub.add_parser("delete", help="delete a key from the OS keyring")
    p.add_argument("name", choices=list(SECRET_NAMES))

    sub.add_parser("status", help="show where each secret is set (no values)")

    a = ap.parse_args(argv)

    if a.cmd == "status":
        for name, src in secret_status().items():
            where = "env" if src["env"] else "keyring" if src["keyring"] else "NOT SET"
            print(f"{name}: {where}")
        if not keyring_available():
            print("(OS keyring unavailable — use .env)")
        return 0

    if a.cmd == "store":
        value = getpass.getpass(f"Enter {a.name} (hidden): ").strip()
        if not value:
            print("empty value — nothing stored")
            return 1
        if store_secret(a.name, value):
            print(f"{a.name} stored in OS keyring")
            return 0
        print(f"keyring unavailable — add {a.name}=... to .env instead")
        return 1

    if a.cmd == "delete":
        if delete_secret(a.name):
            print(f"{a.name} deleted from keyring")
            return 0
        print(f"{a.name} not in keyring (or keyring unavailable)")
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
