"""Tool registration for the run-powershell skill (dogfooded core tool)."""

from jarvis.tools.actions import (
    run_powershell_command,
)
from jarvis.tools.registry import Risk, ToolSpec, RunPowershellParams

register_skill_tool(
    ToolSpec(
        name="run_powershell_command",
        description="Run an allowlisted read-only PowerShell command.",
        params=RunPowershellParams,
        risk=Risk.SYSTEM,
        carries_external_data=True,
        handler=lambda args, cb, nf: run_powershell_command(args.get("command", ""), cb),
    )
)
