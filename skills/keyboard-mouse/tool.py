"""Tool registration for the keyboard-mouse skill (dogfooded core tool)."""

from jarvis.tools.actions import (
    keyboard_mouse_action,
)
from jarvis.tools.registry import Risk, ToolSpec, KeyboardMouseParams

register_skill_tool(
    ToolSpec(
        name="keyboard_mouse_action",
        description="Type text, press keys and hotkeys.",
        params=KeyboardMouseParams,
        risk=Risk.SYSTEM,
        handler=lambda args, cb, nf: keyboard_mouse_action(
            args.get("action", ""), args.get("value", ""), cb
        ),
    )
)
