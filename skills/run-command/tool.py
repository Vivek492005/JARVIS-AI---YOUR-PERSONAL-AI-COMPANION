"""Tool registration for the run-command skill (dogfooded core tool)."""

from jarvis.tools.actions import (
    run_command,
)
from jarvis.tools.registry import Risk, ToolSpec, RunCommandParams

register_skill_tool(
    ToolSpec(
        name="run_command",
        description="Run an allowlisted diagnostic (ipconfig, disk_free).",
        params=RunCommandParams,
        risk=Risk.READ,
        carries_external_data=True,
        handler=lambda args, cb, nf: run_command(args.get("command_key", ""), cb),
    )
)
