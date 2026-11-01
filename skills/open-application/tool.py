"""Tool registration for the open-application skill (dogfooded core tool)."""

from jarvis.tools.actions import (
    open_application,
)
from jarvis.tools.registry import Risk, ToolSpec, OpenApplicationParams

register_skill_tool(ToolSpec(
    name="open_application",
    description="Launch a desktop application by name (Chrome, Notepad, Spotify...).",
    params=OpenApplicationParams,
    risk=Risk.REVERSIBLE,
    handler=lambda args, cb, nf: open_application(args.get("app_name", ""), cb),
))
