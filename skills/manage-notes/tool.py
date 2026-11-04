"""Tool registration for the manage-notes skill (dogfooded core tool)."""

from jarvis.tools.actions import (
    manage_notes,
)
from jarvis.tools.registry import Risk, ToolSpec, ManageNotesParams

register_skill_tool(
    ToolSpec(
        name="manage_notes",
        description="Save, read and clear the user's notes.",
        params=ManageNotesParams,
        risk=Risk.REVERSIBLE,
        carries_external_data=True,
        handler=lambda args, cb, nf: manage_notes(
            args.get("action", ""), args.get("content", None), nf, cb
        ),
    )
)
