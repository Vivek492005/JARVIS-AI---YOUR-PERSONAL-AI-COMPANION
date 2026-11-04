"""Tool registry with risk tiers (Master Plan Task 1.2).

Every executable tool is a declared :class:`ToolSpec`: a pydantic params
model (JSON-schema + validation), a risk tier, a handler, a timeout and
optional scopes. **Nothing executes without a ToolSpec** — unregistered
names are rejected, and arguments are validated before the handler runs.

Risk tiers:
    READ (0)        — only reads state (time, battery, search, describe)
    REVERSIBLE (1)  — can be undone (open app, write note, volume)
    DESTRUCTIVE (2) — data/state loss or outward send (delete, clear, send)
    SYSTEM (3)      — OS-level (lock, shutdown, shell, install)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field


class Risk(IntEnum):
    READ = 0
    REVERSIBLE = 1
    DESTRUCTIVE = 2
    SYSTEM = 3


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    params: type[BaseModel]  # pydantic model = schema + validation
    risk: Risk
    handler: Callable[[Dict[str, Any], Any, str], str]
    timeout_s: float = 15.0
    scopes: frozenset = field(default_factory=frozenset)
    # Task 1.5.1: results from this tool enter the LLM prompt as *data* and
    # are wrapped in <untrusted_data> tags + taint-checked.
    carries_external_data: bool = False


REGISTRY: Dict[str, ToolSpec] = {}


def tool(spec: ToolSpec) -> ToolSpec:
    """Register a ToolSpec. Duplicate names are a programming error."""
    if spec.name in REGISTRY:
        raise ValueError(f"duplicate tool registration: {spec.name}")
    REGISTRY[spec.name] = spec
    return spec


def resolve(tool_name: str, args: Optional[Dict[str, Any]] = None) -> Optional[ToolSpec]:
    """Find the spec for a tool call.

    Sub-action tools are addressed with a dotted name derived from the
    ``action`` argument (e.g. ``system_control.empty_recycle_bin``), so one
    multi-action tool can carry per-action risk tiers. Unknown actions fall
    back to the base tool spec (registered at the *highest* applicable risk,
    i.e. fail-closed).

    ``press_hotkey`` is special: hotkeys on SAFE_HOTKEYS resolve to the
    REVERSIBLE sub-spec, everything else stays at the SYSTEM base tier
    (and the command_policy blocklist still denies the dangerous ones).

    ``uia_invoke`` is special: the button label decides the tier —
    labels like Delete/Send/Pay/Install resolve to the DESTRUCTIVE
    sub-spec, everything else to REVERSIBLE. The label is looked up
    from the UIA backend; if the backend is unavailable we fail closed
    to DESTRUCTIVE.
    """
    from jarvis.policy.command_policy import _normalize_hotkey

    args = args or {}
    action = args.get("action")
    if tool_name == "keyboard_mouse_action" and action == "press_hotkey":
        norm = _normalize_hotkey(args.get("value", ""))
        sub = (
            "keyboard_mouse_action.press_hotkey_safe"
            if norm in SAFE_HOTKEYS
            else "keyboard_mouse_action.press_hotkey_other"
        )
        spec = REGISTRY.get(sub)
        if spec is not None:
            return spec
    if tool_name == "uia_invoke":
        sub = _uia_invoke_subspec(args)
        spec = REGISTRY.get(sub)
        if spec is not None:
            return spec
    if isinstance(action, str) and action:
        sub = REGISTRY.get(f"{tool_name}.{action}")
        if sub is not None:
            return sub
    return REGISTRY.get(tool_name)


def _uia_invoke_subspec(args: Dict[str, Any]) -> str:
    """Pick the uia_invoke sub-spec from the button label.

    Fail-closed: unknown element or missing backend -> destructive tier.
    """
    from jarvis.perception import backends as _backends
    from jarvis.perception.uia import invoke_risk_for_label
    from jarvis.tools.registry import Risk

    element_id = args.get("element_id", "")
    try:
        backend = _backends.get_backend("uia")
    except Exception:
        return "uia_invoke.destructive"
    # Find the element's label without knowing its window: scan the
    # backend's element index when available, else fail closed.
    label = ""
    find = getattr(backend, "find", None)
    get_text = getattr(backend, "get_text", None)
    if get_text is not None:
        try:
            label = get_text(element_id) or ""
        except Exception:
            label = ""
    if not label and find is not None:
        # FakeUIA.by_id fallback for tests; real backends use get_text.
        by_id = getattr(backend, "by_id", {})
        el = by_id.get(element_id)
        if el is not None:
            label = el.name or ""
    if not label:
        return "uia_invoke.destructive"
    risk = invoke_risk_for_label(label)
    return "uia_invoke.destructive" if risk == Risk.DESTRUCTIVE else "uia_invoke.normal"


def function_schemas() -> List[Dict[str, Any]]:
    """OpenAI-compatible function definitions, auto-generated from the registry.

    Only base tools (no dots) are exposed to the LLM; sub-action risk tiers
    are enforced server-side at dispatch.
    """
    schemas = []
    for name in sorted(REGISTRY):
        if "." in name:
            continue
        spec = REGISTRY[name]
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.params.model_json_schema(),
                },
            }
        )
    return schemas


# ---------------------------------------------------------------------------
# Parameter models (one per tool; notes_file-style dispatcher args are NOT
# part of any schema — see A-06)
# ---------------------------------------------------------------------------


class OpenApplicationParams(BaseModel):
    app_name: str = Field(
        ...,
        min_length=1,
        max_length=60,
        description="The common name of the application to launch "
        "(e.g. 'chrome', 'notepad', 'calculator', 'spotify').",
    )


class OpenWebsiteParams(BaseModel):
    url_or_name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="The URL (e.g. 'https://youtube.com') or website name "
        "(e.g. 'youtube', 'github').",
    )


class WebSearchParams(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="The search query.")


class DownloadMediaParams(BaseModel):
    url_or_query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="The media URL or the search term of the song/video.",
    )
    media_type: str = Field(
        default="audio",
        description="Whether to download audio (mp3/m4a) or video (mp4).",
        pattern="^(audio|video)$",
    )


class SystemControlParams(BaseModel):
    action: str = Field(
        ...,
        description="The specific system action to perform.",
        pattern="^(volume_up|volume_down|mute|unmute|take_screenshot|"
        "lock_pc|empty_recycle_bin|check_battery)$",
    )


class KeyboardMouseParams(BaseModel):
    action: str = Field(
        ...,
        description="One of: type_text, press_key, press_hotkey.",
        pattern="^(type_text|press_key|press_hotkey)$",
    )
    value: str = Field(
        default="", description="Text to type, or key/hotkey like 'ctrl+s'.", max_length=2000
    )


class ManageNotesParams(BaseModel):
    action: str = Field(
        ..., description="One of: save, read, clear.", pattern="^(save|read|clear)$"
    )
    content: Optional[str] = Field(
        default=None, max_length=10000, description="Note text (required for 'save')."
    )


class RunPowershellParams(BaseModel):
    command: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="A read-only PowerShell command (validated against the "
        "allowlist; destructive cmdlets are denied).",
    )


class RunCommandParams(BaseModel):
    command_key: str = Field(
        ..., description="Which allowlisted diagnostic to run.", pattern="^(ipconfig|disk_free)$"
    )


# Task 1.4.2: hotkeys on this list are ordinary editing/navigation keys.
SAFE_HOTKEYS = frozenset(
    {
        "ctrl+c",
        "ctrl+v",
        "ctrl+x",
        "ctrl+z",
        "ctrl+s",
        "ctrl+f",
        "ctrl+a",
        "ctrl+t",
        "ctrl+w",
        "ctrl+r",
        "win+d",
    }
)
