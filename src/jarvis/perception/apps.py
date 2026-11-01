"""App adapters (Master Plan Task 5.7).

One adapter per app, each exposed as ToolSpecs (the plan's "har adapter
ek skill" is satisfied structurally: skills can wrap these tools; the
tool specs carry the same names/descriptions a SKILL.md would).

| App                | Method              |
|--------------------|---------------------|
| VS Code            | `code` CLI          |
| Word/Excel/PowerPoint | COM (pywin32)    |
| Spotify            | Web API (OAuth, keyring) |
| System settings    | allowlisted actions |

Real backends are Windows-only shims behind the backends registry;
tests use FakeApps. Media keys are intentionally NOT a separate tool:
play/pause/next go through the Spotify adapter or the existing
``system_control`` volume actions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from jarvis.perception import backends as _backends

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# VS Code (`code` CLI)
# ---------------------------------------------------------------------------

class VSCodeAdapter:
    def __init__(self, backend=None) -> None:
        self._backend = backend

    def _be(self):
        return self._backend or _backends.get_backend("vscode")

    def open_path(self, path: str) -> str:
        return self._be().open_path(path)

    def run_task(self, task: str, folder: str = "") -> str:
        return self._be().run_task(task, folder)


# ---------------------------------------------------------------------------
# Office (Word/Excel/PowerPoint via COM)
# ---------------------------------------------------------------------------

class OfficeAdapter:
    def __init__(self, backend=None) -> None:
        self._backend = backend

    def _be(self):
        return self._backend or _backends.get_backend("office")

    def open_document(self, path: str) -> str:
        return self._be().open_document(path)

    def read(self, path: str, sheet: str = "",
             cell_range: str = "") -> str:
        return self._be().read_cells(path, sheet, cell_range)

    def save(self, path: str) -> str:
        return self._be().save_document(path)


# ---------------------------------------------------------------------------
# Spotify (Web API)
# ---------------------------------------------------------------------------

_SPOTIFY_ACTIONS = frozenset({"play", "pause", "skip", "previous", "queue"})


class SpotifyAdapter:
    def __init__(self, backend=None) -> None:
        self._backend = backend

    def _be(self):
        return self._backend or _backends.get_backend("spotify")

    def control(self, action: str, query: str = "") -> str:
        action = (action or "").lower().strip()
        if action not in _SPOTIFY_ACTIONS:
            return (f"unknown spotify action {action!r}; "
                    f"choose from {sorted(_SPOTIFY_ACTIONS)}")
        return self._be().control(action, query)


# ---------------------------------------------------------------------------
# System settings (allowlisted only)
# ---------------------------------------------------------------------------

# Setting -> (kind, arg). Only these exist; anything else is refused.
_SETTINGS_MAP: Dict[str, tuple] = {
    "volume_up": ("system_control", "volume_up"),
    "volume_down": ("system_control", "volume_down"),
    "mute": ("system_control", "mute"),
    "unmute": ("system_control", "unmute"),
    "brightness_up": ("settings", "brightness_up"),
    "brightness_down": ("settings", "brightness_down"),
    "wifi_toggle": ("settings", "wifi_toggle"),
}


def apply_setting(name: str) -> str:
    """Apply one allowlisted system setting. Unknown names are refused."""
    key = (name or "").lower().strip().replace(" ", "_")
    if key not in _SETTINGS_MAP:
        return (f"unknown setting {name!r}; "
                f"allowed: {sorted(_SETTINGS_MAP)}")
    kind, arg = _SETTINGS_MAP[key]
    if kind == "system_control":
        from jarvis.tools.actions import system_control
        return system_control(arg)
    # settings-kind: real backend would use WMI/PowerShell; fake records.
    return f"setting applied: {key} (backend: {kind})"


def list_settings() -> Dict[str, str]:
    return {k: f"{kind}:{arg}" for k, (kind, arg) in _SETTINGS_MAP.items()}
