"""Thin clients over JarvisService (Master Plan Task 2.4).

:class:`JarvisClient` is the in-process client (used by the tkinter UI and
tests). :class:`HttpJarvisClient` talks to a running ``jarvis serve --http``
over the token-secured HTTP API. A WebSocket event-stream client arrives
with the Phase 6 integrations (needs a WS client lib on Windows).
"""

from __future__ import annotations

from typing import Callable, Optional

from jarvis.core.events import Event
from jarvis.core.lanes import CancelToken, Priority
from jarvis.server.service import JarvisService


class JarvisClient:
    """In-process client: the same calls the HTTP API exposes."""

    def __init__(self, service: JarvisService) -> None:
        self._service = service

    # -- commands ------------------------------------------------------
    def send_command(self, text: str,
                     priority: Priority = Priority.TASK) -> CancelToken:
        return self._service.submit_command(text, priority=priority)

    def send_text_command(self, text: str) -> Optional[CancelToken]:
        """GUI-compatible alias (``JARVISGUI`` calls this)."""
        if not text or not text.strip():
            return None
        return self.send_command(text)

    def interrupt(self, reason: str = "") -> None:
        self._service.interrupt(reason=reason)

    # -- state / events ------------------------------------------------
    def get_state(self) -> dict:
        return self._service.get_state()

    def subscribe(self, etype: type[Event], fn: Callable[[Event], None]):
        return self._service.on_event(etype, fn)


class HttpJarvisClient:
    """HTTP client for ``jarvis serve --http`` (token-secured)."""

    def __init__(self, base_url: str, token: str) -> None:
        try:
            import httpx
        except ImportError as e:
            raise RuntimeError("HttpJarvisClient needs httpx installed") from e
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    def health(self) -> dict:
        r = self._http.get("/health")
        r.raise_for_status()
        return r.json()

    def get_state(self) -> dict:
        r = self._http.get("/state")
        r.raise_for_status()
        return r.json()

    def send_command(self, text: str, priority: str = "TASK") -> dict:
        r = self._http.post("/command", json={"text": text, "priority": priority})
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._http.close()
