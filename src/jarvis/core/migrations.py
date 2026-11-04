"""settings.toml schema migrations (Task 8.3).

``SETTINGS_SCHEMA_VERSION`` is stored as ``schema_version`` at the top of
settings.toml. On load, :func:`migrate_settings` walks the data forward
through every migration — old installs keep working after an update, and
unknown future versions are left untouched (fail-open for the user's own
keys, never destructive).
"""

from __future__ import annotations

from typing import Any, Callable, Dict

SETTINGS_SCHEMA_VERSION = 1


def _migrate_0_to_1(data: Dict[str, Any]) -> Dict[str, Any]:
    """v0 -> v1: introduce [safety].safe_mode and [privacy].offline."""
    data.setdefault("safety", {}).setdefault("safe_mode", False)
    data.setdefault("privacy", {}).setdefault("offline", False)
    data.setdefault("privacy", {}).setdefault("crash_upload", False)
    data["schema_version"] = 1
    return data


_MIGRATIONS: Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    0: _migrate_0_to_1,
}


def migrate_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Apply pending migrations. Pure function — safe to call repeatedly."""
    data = dict(data)
    version = int(data.get("schema_version", 0))
    while version in _MIGRATIONS:
        data = _MIGRATIONS[version](dict(data))
        version = int(data.get("schema_version", version + 1))
    return data


def needs_migration(data: Dict[str, Any]) -> bool:
    return int(data.get("schema_version", 0)) < SETTINGS_SCHEMA_VERSION
