"""Tool registration for the download-media skill (dogfooded core tool)."""

from jarvis.tools.actions import (
    download_media,
)
from jarvis.tools.registry import Risk, ToolSpec, DownloadMediaParams

register_skill_tool(ToolSpec(
    name="download_media",
    description="Download audio/video from a URL or search term.",
    params=DownloadMediaParams,
    risk=Risk.REVERSIBLE,
    handler=lambda args, cb, nf: download_media(args.get("url_or_query", ""), args.get("media_type", "audio"), cb),
))
