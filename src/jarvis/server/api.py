"""jarvisd HTTP + WebSocket API (Master Plan Task 2.4).

Security (plan §2.4):
  * binds 127.0.0.1 only (see cli.py),
  * per-install random bearer <redacted> (server.token),
  * token on every HTTP call (Authorization header) and on the WebSocket
    handshake (``?token=`` query param or Authorization header),
  * CORS off.

Protocol: JSON, versioned (``"v": 1``).

Requires the ``server`` extra: ``pip install jarvis-assistant[server]``.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel

from jarvis.core.events import Event
from jarvis.core.lanes import Priority
from jarvis.server.service import JarvisService
from jarvis.server.token import bearer_ok

logger = logging.getLogger(__name__)

try:
    from fastapi import (Depends, FastAPI, Header, HTTPException, Query,
                         WebSocket, WebSocketDisconnect)
    from fastapi.responses import FileResponse, JSONResponse
    _FASTAPI_AVAILABLE = True
except ImportError:  # the 'server' extra is optional
    _FASTAPI_AVAILABLE = False


class CommandIn(BaseModel):
    """POST /command body."""
    text: str
    priority: str = "TASK"


def event_to_dict(ev: Event) -> Dict[str, Any]:
    """Serialize an event to the v1 JSON protocol."""
    d: Dict[str, Any] = {"v": 1, "type": type(ev).__name__,
                         "trace": ev.trace, "ts": ev.ts}
    for f in dataclasses.fields(ev):
        if f.name in ("trace", "ts"):
            continue
        d[f.name] = getattr(ev, f.name)
    return d


def create_app(service: JarvisService, token: str):
    """Build the jarvisd FastAPI application."""
    if not _FASTAPI_AVAILABLE:
        raise RuntimeError(
            "jarvisd HTTP API needs the 'server' extra: "
            "pip install jarvis-assistant[server]")

    app = FastAPI(title="jarvisd", version="1")

    async def verify(authorization: Optional[str] = Header(default=None)):
        if not bearer_ok(authorization, token):
            raise HTTPException(status_code=401, detail="invalid token")

    # --- HUD (Task 7.2): event-driven state machine + static web UI --------
    from jarvis.hud.state import HUDStateMachine
    hud = HUDStateMachine()
    service.bus.on_all(hud.on_event)

    _HUD_STATIC = Path(__file__).resolve().parent.parent / "hud" / "static"
    _HUD_FILES = {
        "index.html": "text/html",
        "styles.css": "text/css",
        "app.js": "text/javascript",
        "manifest.json": "application/manifest+json",
        "sw.js": "text/javascript",
    }

    def _hud_file(name: str) -> "FileResponse":
        # No path traversal: only exact allowlisted names, joined under the
        # package's static dir.
        if name not in _HUD_FILES:
            raise HTTPException(status_code=404, detail="not found")
        path = _HUD_STATIC / name
        if not path.is_file():
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(path, media_type=_HUD_FILES[name])

    @app.get("/hud", dependencies=[Depends(verify)], include_in_schema=False)
    async def hud_index():
        return _hud_file("index.html")

    # NOTE: /hud/snapshot must be registered BEFORE /hud/{name},
    # otherwise the path param swallows it.
    @app.get("/hud/snapshot", dependencies=[Depends(verify)])
    async def hud_snapshot():
        return JSONResponse(hud.snapshot())

    @app.get("/hud/{name}", dependencies=[Depends(verify)],
             include_in_schema=False)
    async def hud_static(name: str):
        return _hud_file(name)

    class CommandIn(BaseModel):
        text: str
        priority: str = "TASK"

    @app.get("/health")
    async def health():
        from jarvis import __version__
        return {"v": 1, "status": "ok", "version": __version__}

    @app.get("/state", dependencies=[Depends(verify)])
    async def state():
        return JSONResponse(service.get_state())

    @app.post("/command", dependencies=[Depends(verify)])
    async def command(cmd: CommandIn):
        try:
            prio = Priority[cmd.priority.upper()]
        except KeyError:
            raise HTTPException(status_code=400,
                                detail=f"unknown priority {cmd.priority!r}") from None
        try:
            service.submit_command(cmd.text, priority=prio)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None
        return {"v": 1, "accepted": True}

    @app.websocket("/events")
    async def events(ws: WebSocket, token_q: Optional[str] = Query(default=None, alias="token")):
        # Token via ?token= or Authorization header (browsers can't set
        # headers on a WS handshake, hence the query param).
        auth_header = ws.headers.get("authorization")
        ok = bearer_ok(auth_header, token) or (
            token_q is not None and bearer_ok(f"Bearer {token_q}", token))
        if not ok:
            await ws.close(code=4401)
            return
        await ws.accept()
        loop = asyncio.get_running_loop()
        aq: asyncio.Queue = asyncio.Queue()

        # Bus subscribers are sync: hop onto the loop thread-safely.
        def _on_event(ev: Event) -> None:
            loop.call_soon_threadsafe(aq.put_nowait, event_to_dict(ev))

        service.bus.on_all(_on_event)

        async def _reader():
            # Raises WebSocketDisconnect when the client goes away; that is
            # how we notice a disconnect while idle (no events flowing).
            while True:
                await ws.receive_text()

        reader = asyncio.create_task(_reader())
        try:
            await ws.send_json({"v": 1, "type": "hello"})
            while True:
                get_task = asyncio.create_task(aq.get())
                done, _pending = await asyncio.wait(
                    {get_task, reader}, return_when=asyncio.FIRST_COMPLETED)
                if reader in done:
                    get_task.cancel()
                    # Surface close errors (but not the normal disconnect).
                    try:
                        reader.result()
                    except WebSocketDisconnect:
                        pass
                    break
                await ws.send_json(get_task.result())
        finally:
            reader.cancel()
            service.bus.off(Event, _on_event)  # off() also removes on_all subs

    return app
