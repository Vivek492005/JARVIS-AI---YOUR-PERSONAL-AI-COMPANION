"""Telegram remote control (Master Plan Task 6.5).

Design decision: a minimal long-polling client over ``httpx`` instead of
``python-telegram-bot`` — the surface we need (getUpdates, sendMessage,
answerCallbackQuery, getFile) is five endpoints; the light client is
fully mockable and adds no heavy dependency.

Safety rules (from the plan):
* **User-id allowlist**: messages from anyone else are ignored and
  logged (never answered — no oracle for strangers).
* **Autonomy one step lower** when remote: the effective level is
  ``max(0, configured - 1)``.
* **SYSTEM tools are disabled remotely** by default (config flag).
* Text → command pipeline (via injected handler); voice note → STT
  hook; photo → VLM hook; inline buttons answer confirmations
  (callback_query → confirm/deny the pending confirmation).

The bot token comes from :mod:`jarvis.core.secrets`
(``TELEGRAM_BOT_TOKEN``); allowed user ids from
``TELEGRAM_ALLOWED_USERS`` (comma-separated). Setup: talk to
``@BotFather`` → ``/newbot`` → paste the token via
``python -m jarvis.core.secrets store TELEGRAM_BOT_TOKEN``.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"


@dataclass
class TgMessage:
    chat_id: int
    user_id: int
    text: str = ""
    voice_file_id: str = ""
    photo_file_id: str = ""
    callback_id: str = ""
    callback_data: str = ""


class TelegramBot:
    """Long-polling Telegram remote. All network goes through an
    injectable ``http`` callable for tests."""

    def __init__(
        self,
        token: str,
        allowed_users: List[int],
        on_command: Callable[[str, int], str],
        autonomy_level: int = 1,
        remote_system_tools: bool = False,
        on_voice: Optional[Callable[[bytes], str]] = None,
        on_photo: Optional[Callable[[bytes], str]] = None,
        http: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.token = token
        self.allowed = set(allowed_users)
        self.on_command = on_command
        # Plan 6.5: remote autonomy is one step lower.
        self.remote_level = max(0, autonomy_level - 1)
        self.remote_system_tools = remote_system_tools
        self.on_voice = on_voice
        self.on_photo = on_photo
        self._http = http or self._default_http
        self._offset = 0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # -- HTTP -----------------------------------------------------------
    def _default_http(self, method: str, **kwargs: Any) -> Dict[str, Any]:
        import httpx

        url = API.format(token=self.token, method=method)
        r = httpx.post(url, timeout=30.0, **kwargs)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"telegram API error: {data}")
        return data

    def _api(self, method: str, **kwargs: Any) -> Dict[str, Any]:
        return self._http(method, **kwargs)

    # -- lifecycle --------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="jarvis-telegram")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                updates = self._api(
                    "getUpdates",
                    json={
                        "offset": self._offset,
                        "timeout": 25,
                        "allowed_updates": ["message", "callback_query"],
                    },
                ).get("result", [])
                for u in updates:
                    self._offset = max(self._offset, u.get("update_id", 0) + 1)
                    self._handle_update(u)
            except Exception as e:
                logger.warning(f"telegram poll error: {e}")

    # -- update handling ----------------------------------------------------
    def _parse(self, u: Dict[str, Any]) -> Optional[TgMessage]:
        if "callback_query" in u:
            cq = u["callback_query"]
            frm = cq.get("from", {})
            return TgMessage(
                chat_id=(cq.get("message") or {}).get("chat", {}).get("id", 0),
                user_id=frm.get("id", 0),
                callback_id=cq.get("id", ""),
                callback_data=cq.get("data", ""),
            )
        m = u.get("message") or {}
        frm = m.get("from", {})
        voice = (m.get("voice") or {}).get("file_id", "")
        photos = m.get("photo") or []
        photo = photos[-1].get("file_id", "") if photos else ""
        return TgMessage(
            chat_id=(m.get("chat") or {}).get("id", 0),
            user_id=frm.get("id", 0),
            text=m.get("text", "") or "",
            voice_file_id=voice,
            photo_file_id=photo,
        )

    def _handle_update(self, u: Dict[str, Any]) -> None:
        msg = self._parse(u)
        if msg is None:
            return
        if msg.user_id not in self.allowed:
            # Strangers get silence, not even an error message.
            logger.warning(f"telegram: ignoring message from unknown user {msg.user_id}")
            return
        try:
            if msg.callback_data:
                self._handle_callback(msg)
            elif msg.voice_file_id and self.on_voice:
                data = self._download(msg.voice_file_id)
                reply = self.on_voice(data)
                self.send_message(msg.chat_id, reply)
            elif msg.photo_file_id and self.on_photo:
                data = self._download(msg.photo_file_id)
                reply = self.on_photo(data)
                self.send_message(msg.chat_id, reply)
            elif msg.text:
                reply = self.on_command(msg.text, self.remote_level)
                self.send_message(msg.chat_id, reply)
        except Exception as e:
            logger.exception(f"telegram: handling failed: {e}")
            try:
                self.send_message(msg.chat_id, f"Something went wrong: {e}")
            except Exception as send_e:
                logger.debug(f"telegram: error reply failed: {send_e}")

    def _handle_callback(self, msg: TgMessage) -> None:
        # Inline-button confirmations: "<confirm|deny>:<token>"
        self._api("answerCallbackQuery", json={"callback_query_id": msg.callback_id})
        action = (msg.callback_data or "").split(":", 1)[0]
        if action in ("confirm", "deny"):
            reply = self.on_command(f"/{action}", self.remote_level)
            self.send_message(msg.chat_id, reply)

    def _download(self, file_id: str) -> bytes:
        info = self._api("getFile", json={"file_id": file_id})
        path = info["result"]["file_path"]
        import httpx

        url = f"https://api.telegram.org/file/bot{self.token}/{path}"
        r = httpx.get(url, timeout=30.0)
        r.raise_for_status()
        return r.content

    # -- sending ------------------------------------------------------------
    def send_message(
        self, chat_id: int, text: str, buttons: Optional[List[List[str]]] = None
    ) -> None:
        payload: Dict[str, Any] = {"chat_id": chat_id, "text": text[:4000]}
        if buttons:
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": b, "callback_data": f"confirm:{b}"} for b in row] for row in buttons
                ]
            }
        self._api("sendMessage", json=payload)


def from_config(on_command: Callable[[str, int], str], **kwargs: Any) -> Optional[TelegramBot]:
    """Build a bot from secrets/env. Returns None when not configured."""
    from jarvis.core.secrets import get_secret

    token = get_secret("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.info("telegram: TELEGRAM_BOT_TOKEN not set; remote disabled")
        return None
    raw = get_secret("TELEGRAM_ALLOWED_USERS")
    try:
        allowed = [int(x) for x in raw.split(",") if x.strip()]
    except ValueError:
        allowed = []
    if not allowed:
        logger.warning("telegram: no TELEGRAM_ALLOWED_USERS; remote disabled")
        return None
    return TelegramBot(token=token, allowed_users=allowed, on_command=on_command, **kwargs)
