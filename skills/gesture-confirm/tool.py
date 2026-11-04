"""Tool registration for the gesture-confirm skill (Task 7.8).

The tool itself is thin: all logic lives in jarvis.perception.gesture_gate
so it stays testable without a camera. The legacy MediaPipe controller is
imported lazily inside the gate — this skill is optional and must load even
when mediapipe/opencv aren't installed.
"""

from pydantic import BaseModel, Field

from jarvis.perception.gesture_gate import await_gesture, gesture_available
from jarvis.tools.registry import Risk, ToolSpec


class GestureConfirmParams(BaseModel):
    """Timeout in seconds to wait for the gesture (default 15)."""

    timeout_s: float = Field(default=15.0, ge=1.0, le=60.0)


def _handler(args, cb, nf) -> str:
    ok, reason = gesture_available()
    if not ok:
        return f"unavailable: {reason}"
    timeout = float((args or {}).get("timeout_s") or 15.0)
    return await_gesture(timeout_s=min(max(timeout, 1.0), 60.0))


register_skill_tool(
    ToolSpec(
        name="gesture_confirm",
        description=(
            "Camera se thumbs-up (haan) / thumbs-down (nahi) lekar "
            "confirmation ka jawab deta hai. Camera sirf confirmation "
            "window ke liye khulta hai; frames kabhi save nahi hote."
        ),
        params=GestureConfirmParams,
        risk=Risk.REVERSIBLE,
        handler=_handler,
    )
)
