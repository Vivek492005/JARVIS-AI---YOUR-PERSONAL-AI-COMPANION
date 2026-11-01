"""ToolSpec registrations for Phase-5 perception/control tools.

Each task module exposes its specs; :func:`register_perception_tools`
registers them idempotently. Called from
:func:`jarvis.tools.actions._register_tools` so every new surface goes
through the single policy gate (``run_action``) like all other tools.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from jarvis.tools.registry import REGISTRY, Risk, ToolSpec, tool


def _reg(spec: ToolSpec) -> ToolSpec:
    if spec.name in REGISTRY:
        return REGISTRY[spec.name]
    return tool(spec)


# ---------------------------------------------------------------------------
# 5.2 UIA tools
# ---------------------------------------------------------------------------

class DescribeScreenParams(BaseModel):
    handle: Optional[int] = Field(
        default=None, description="Window handle; default = active window.")
    depth: int = Field(default=3, ge=1, le=6,
                       description="Tree depth for the compact dump.")


class UiaFindParams(BaseModel):
    name: Optional[str] = Field(default=None, description="Substring of the control name.")
    role: Optional[str] = Field(default=None, description="Control role, e.g. 'button'.")
    automation_id: Optional[str] = Field(default=None)
    handle: Optional[int] = Field(default=None, description="Window handle; default = active.")


class UiaInvokeParams(BaseModel):
    element_id: str = Field(..., min_length=1, description="Element id from describe_screen/uia_find.")


class UiaGetTextParams(BaseModel):
    element_id: str = Field(..., min_length=1)


class UiaSetTextParams(BaseModel):
    element_id: str = Field(..., min_length=1)
    value: str = Field(..., max_length=10000)


def _h_describe_screen(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    from jarvis.perception.uia import controller
    from jarvis.perception.privacy import SensitiveWindowError
    try:
        return controller().describe_screen(handle=args.get("handle"),
                                            depth=args.get("depth", 3))
    except SensitiveWindowError as e:
        return f"Blocked: {e}"


def _h_uia_find(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    from jarvis.perception.uia import controller
    from jarvis.perception.privacy import SensitiveWindowError
    try:
        el = controller().find(name=args.get("name"), role=args.get("role"),
                               automation_id=args.get("automation_id"),
                               handle=args.get("handle"))
    except SensitiveWindowError as e:
        return f"Blocked: {e}"
    if el is None:
        return "no matching element"
    return f"[{el.role}] '{el.name}' #{el.element_id}"


def _h_uia_invoke(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    from jarvis.perception.uia import controller
    return controller().invoke(args["element_id"])


def _h_uia_get_text(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    from jarvis.perception.uia import controller
    return controller().get_text(args["element_id"])


def _h_uia_set_text(args: Dict[str, Any], _cb: Any, _nf: str) -> str:
    from jarvis.perception.uia import controller
    return controller().set_text(args["element_id"], args["value"])


def _uia_specs() -> List[ToolSpec]:
    base_invoke = dict(description="Clicks/invokes a UI element by id. "
                                   "Destructive labels (Delete/Send/Pay/...) "
                                   "escalate to DESTRUCTIVE automatically.",
                       params=UiaInvokeParams, handler=_h_uia_invoke)
    return [
        ToolSpec(name="describe_screen", risk=Risk.READ,
                 description="Compact accessibility tree of the active window "
                             "(role, name, id). Refuses sensitive windows.",
                 params=DescribeScreenParams, handler=_h_describe_screen,
                 carries_external_data=True),
        ToolSpec(name="uia_find", risk=Risk.READ,
                 description="Find a UI control by name/role/automation_id.",
                 params=UiaFindParams, handler=_h_uia_find),
        ToolSpec(name="uia_invoke", risk=Risk.REVERSIBLE, **base_invoke),
        ToolSpec(name="uia_invoke.normal", risk=Risk.REVERSIBLE,
                 description="Invoke a non-destructive control.",
                 params=UiaInvokeParams, handler=_h_uia_invoke),
        ToolSpec(name="uia_invoke.destructive", risk=Risk.DESTRUCTIVE,
                 description="Invoke a destructive control (Delete/Send/Pay/...).",
                 params=UiaInvokeParams, handler=_h_uia_invoke),
        ToolSpec(name="uia_get_text", risk=Risk.READ,
                 description="Read text of a UI element.",
                 params=UiaGetTextParams, handler=_h_uia_get_text,
                 carries_external_data=True),
        ToolSpec(name="uia_set_text", risk=Risk.REVERSIBLE,
                 description="Type text into a UI element.",
                 params=UiaSetTextParams, handler=_h_uia_set_text),
    ]


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

def register_perception_tools() -> None:
    """Idempotent registration of all Phase-5 tool specs."""
    for spec in _uia_specs():
        _reg(spec)
