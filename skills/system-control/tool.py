"""Tool registration for the system-control skill (dogfooded core tool)."""

from jarvis.tools.actions import (
    system_control,
)
from jarvis.tools.registry import Risk, ToolSpec, SystemControlParams

register_skill_tool(ToolSpec(
    name="system_control",
    description="Volume, mute, screenshot, battery, lock PC, empty recycle bin.",
    params=SystemControlParams,
    risk=Risk.SYSTEM,
    handler=lambda args, cb, nf: system_control(args.get("action", ""), cb),
))
