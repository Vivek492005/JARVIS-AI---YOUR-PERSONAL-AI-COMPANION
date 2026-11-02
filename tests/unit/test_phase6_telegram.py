"""Tests for Task 6.5 (Telegram remote control)."""

from jarvis.integrations.telegram import TelegramBot, from_config


class FakeHttp:
    """Records API calls; canned getUpdates."""

    def __init__(self, updates):
        self.updates = updates
        self.sent = []
        self.answered = []

    def __call__(self, method, **kwargs):
        if method == "getUpdates":
            res = self.updates
            self.updates = []
            return {"ok": True, "result": res}
        if method == "sendMessage":
            self.sent.append(kwargs["json"])
            return {"ok": True, "result": {}}
        if method == "answerCallbackQuery":
            self.answered.append(kwargs["json"])
            return {"ok": True, "result": True}
        if method == "getFile":
            return {"ok": True,
                    "result": {"file_path": "voice/file.ogg"}}
        raise AssertionError(f"unexpected {method}")


def _msg(uid, text, mid=1):
    return {"update_id": mid,
            "message": {"message_id": mid,
                        "from": {"id": uid},
                        "chat": {"id": 99},
                        "text": text}}


def test_unknown_user_ignored_silently():
    http = FakeHttp([_msg(666, "hello")])
    seen = []
    bot = TelegramBot(token="t", allowed_users=[1],
                      on_command=lambda text, lvl: seen.append(text) or "x",
                      http=http)
    bot._handle_update(http.updates[0])
    assert seen == [] and http.sent == []


def test_text_goes_to_command_with_lowered_autonomy():
    http = FakeHttp([_msg(1, "battery?")])
    seen = []
    bot = TelegramBot(token="t", allowed_users=[1], autonomy_level=2,
                      on_command=lambda text, lvl: seen.append((text, lvl))
                      or "ok", http=http)
    bot._handle_update(http.updates[0])
    assert seen == [("battery?", 1)]               # one step lower
    assert http.sent[0]["chat_id"] == 99
    assert "ok" in http.sent[0]["text"]


def test_remote_level_never_negative():
    bot = TelegramBot(token="t", allowed_users=[1], autonomy_level=0,
                      on_command=lambda t, l: "x")
    assert bot.remote_level == 0


def test_callback_confirm_deny():
    http = FakeHttp([{
        "update_id": 5,
        "callback_query": {"id": "cq1", "from": {"id": 1},
                           "message": {"chat": {"id": 99}},
                           "data": "confirm:abc123"},
    }])
    seen = []
    bot = TelegramBot(token="t", allowed_users=[1],
                      on_command=lambda text, lvl: seen.append(text) or "done",
                      http=http)
    bot._handle_update(http.updates[0])
    assert http.answered and seen == ["/confirm"]


def test_voice_note_routes_to_stt_hook(monkeypatch):
    import httpx

    class R:
        content = b"oggbytes"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(httpx, "get", lambda *a, **k: R())
    http = FakeHttp([{"update_id": 7,
                      "message": {"message_id": 7, "from": {"id": 1},
                                  "chat": {"id": 99},
                                  "voice": {"file_id": "v1"}}}])
    bot = TelegramBot(token="t", allowed_users=[1],
                      on_command=lambda t, l: "x",
                      on_voice=lambda data: f"heard {len(data)} bytes",
                      http=http)
    bot._handle_update(http.updates[0])
    assert "heard 8 bytes" in http.sent[0]["text"]


def test_from_config_requires_token_and_users(monkeypatch):
    import jarvis.core.secrets as sec
    monkeypatch.setattr(sec, "get_secret", lambda n: "")
    assert from_config(lambda t, l: "x") is None
    monkeypatch.setattr(sec, "get_secret",
                        lambda n: "tok" if n == "TELEGRAM_BOT_TOKEN" else "")
    assert from_config(lambda t, l: "x") is None   # no allowed users


def test_from_config_builds(monkeypatch):
    import jarvis.core.secrets as sec
    vals = {"TELEGRAM_BOT_TOKEN": "tok123",
            "TELEGRAM_ALLOWED_USERS": "111, 222"}
    monkeypatch.setattr(sec, "get_secret", lambda n: vals.get(n, ""))
    bot = from_config(lambda t, l: "x", autonomy_level=3)
    assert bot is not None and bot.allowed == {111, 222}
    assert bot.remote_level == 2


def test_remote_system_deny_by_default():
    from jarvis.policy import PolicyContext, decide, Decision
    from jarvis.tools.registry import resolve
    spec = resolve("system_control", {"action": "lock_pc"})
    assert spec is not None
    # local: CONFIRM; remote without opt-in: DENY
    assert decide(spec, PolicyContext(), 1) == Decision.CONFIRM
    assert decide(spec, PolicyContext(remote=True), 1) == Decision.DENY
    # explicit opt-in restores CONFIRM
    assert decide(spec, PolicyContext(remote=True,
                                      remote_system_tools=True),
                  1) == Decision.CONFIRM
