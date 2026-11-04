"""Tests for the JARVIS chat UI: /hud/chat.* routes, POST /interrupt,
and the tray/hotkey summon wiring in cli.py."""

import sys
import time
import types
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, "src")


def _make_client(monkeypatch, service=None):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from jarvis.server import api as api_mod

    monkeypatch.setattr(api_mod, "_FASTAPI_AVAILABLE", True)
    if service is None:
        service = MagicMock()
        service.bus = MagicMock()
    app = api_mod.create_app(service, token="sekrit")
    return TestClient(app)


def test_chat_routes_require_auth(monkeypatch):
    c = _make_client(monkeypatch)
    assert c.get("/hud/chat.html").status_code == 401
    assert c.get("/hud/chat.js").status_code == 401
    assert c.get("/hud/chat.css").status_code == 401
    assert c.get("/hud/buddy.html").status_code == 401
    assert c.get("/hud/buddy.js").status_code == 401
    assert c.get("/hud/buddy.css").status_code == 401
    assert c.post("/interrupt").status_code == 401


def test_chat_serves_pages_and_assets(monkeypatch):
    c = _make_client(monkeypatch)
    h = {"Authorization": "Bearer sekrit"}
    for name, ctype, marker in [
        ("chat.html", "text/html", 'id="chat-app"'),
        ("chat.js", "text/javascript", "renderMarkdown"),
        ("chat.css", "text/css", "--accent"),
        ("buddy.html", "text/html", 'id="buddy"'),
        ("buddy.js", "text/javascript", "JarvisBuddy"),
        ("buddy.css", "text/css", ".buddy-body"),
    ]:
        r = c.get(f"/hud/{name}", headers=h)
        assert r.status_code == 200, name
        assert r.headers["content-type"].startswith(ctype), name
        assert marker in r.text, name


def test_chat_html_never_inlines_unescaped_model_output(monkeypatch):
    # The page must not contain patterns that would eval/inject; the JS
    # renderer is the only HTML path and it escapes first.
    c = _make_client(monkeypatch)
    h = {"Authorization": "Bearer sekrit"}
    js = c.get("/hud/chat.js", headers=h).text
    assert "escapeHtml" in js
    assert "innerHTML = renderMarkdown" in js or "innerHTML=renderMarkdown" in js \
        or 'bubble.innerHTML = renderMarkdown' in js


def test_interrupt_calls_service(monkeypatch):
    c = _make_client(monkeypatch)
    h = {"Authorization": "Bearer sekrit"}
    # reach back to the mock service via the app is awkward; instead build
    # with an explicit mock and assert on it.
    service = MagicMock()
    service.bus = MagicMock()
    c2 = _make_client(monkeypatch, service=service)
    r = c2.post("/interrupt", headers=h)
    assert r.status_code == 200
    assert r.json()["interrupted"] is True
    service.interrupt.assert_called_once_with(reason="chat-stop")


def test_interrupt_501_without_service_support(monkeypatch):
    service = types.SimpleNamespace(bus=MagicMock())  # no .interrupt
    c = _make_client(monkeypatch, service=service)
    h = {"Authorization": "Bearer sekrit"}
    r = c.post("/interrupt", headers=h)
    assert r.status_code == 501


# --- summon wiring ------------------------------------------------------


def _fake_tray_modules(monkeypatch):
    import webbrowser
    import jarvis.hud.tray as tray_mod
    from jarvis import cli as cli_mod

    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url))
    created = {}

    class FakeTray:
        def __init__(self, backend=None, on_show=None, on_summon=None,
                     on_quit=None):
            created["tray"] = self
            self.on_show = on_show
            self.on_summon = on_summon

        @property
        def available(self):
            return True

        def run(self):
            created["tray_ran"] = True

    class FakeHotkey:
        def __init__(self, on_summon, hotkey=None, backend=None):
            created["hotkey"] = self
            self.on_summon = on_summon
            self.hotkey = hotkey or "ctrl+alt+j"

        @property
        def available(self):
            return True

        def start(self):
            created["hotkey_started"] = True

    monkeypatch.setattr(tray_mod, "TrayController", FakeTray)
    monkeypatch.setattr(tray_mod, "HotkeySummon", FakeHotkey)
    return cli_mod, opened, created


def test_summon_opens_chat_with_token(monkeypatch):
    cli_mod, opened, created = _fake_tray_modules(monkeypatch)
    cli_mod._start_summon_ui(8765, "sekrit")
    deadline = time.time() + 5
    while "tray_ran" not in created and time.time() < deadline:
        time.sleep(0.01)
    assert created.get("tray_ran") is True
    assert created.get("hotkey_started") is True
    created["tray"].on_show()
    assert opened == ["http://127.0.0.1:8765/hud/buddy.html?token=sekrit"]
    created["hotkey"].on_summon()
    assert len(opened) == 2
    assert opened[1].endswith("/hud/buddy.html?token=sekrit")


def test_summon_never_raises(monkeypatch):
    import jarvis.hud.tray as tray_mod
    from jarvis import cli as cli_mod

    class BoomTray:
        def __init__(self, *a, **k):
            raise RuntimeError("no tray here")

    monkeypatch.setattr(tray_mod, "TrayController", BoomTray)
    # Must not raise: serve must survive a broken tray stack.
    cli_mod._start_summon_ui(8765, "sekrit")
