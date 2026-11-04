"""Tool registration for the open-website skill (dogfooded core tool)."""

from jarvis.tools.actions import (
    open_website,
)
from jarvis.tools.registry import Risk, ToolSpec, OpenWebsiteParams

register_skill_tool(
    ToolSpec(
        name="open_website",
        description="Open a URL or named website in the default browser.",
        params=OpenWebsiteParams,
        risk=Risk.REVERSIBLE,
        handler=lambda args, cb, nf: open_website(args.get("url_or_name", ""), cb),
    )
)
