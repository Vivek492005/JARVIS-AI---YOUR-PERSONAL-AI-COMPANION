"""Tests for the HUD state machine (Task 7.2) and /hud server routes."""

import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, "src")

from jarvis.core.events import (
    ConfirmationAnswered,
    ConfirmationRequested,
    Error,
    SpeechStarted,
    SpeechStopped,
    ToolFinished,
    ToolRequested,
    UtteranceFinal,
    UtterancePartial,
    WakeDetected,
)
from jarvis.hud.state import (
    CONFIRMING,
    ERROR,
    IDLE,
    LISTENING,
    SPEAKING,
    STATES,
    THINKING,
    HUDStateMachine,
)


def test_all_six_states_reachable():
    h = HUDStateMachine()
    assert h.state == IDLE
    h.on_event(WakeDetected())
    assert h.state == LISTENING
    h.on_event(UtteranceFinal(text="hi"))
    assert h.state == THINKING
    h.on_event(ConfirmationRequested(tool="x", question="q?"))
    assert h.state == CONFIRMING
    h.on_event(ConfirmationAnswered(confirmed=True, tool="x"))
    assert h.state == THINKING
    h.on_event(SpeechStarted(text="hello"))
    assert h.state == SPEAKING
    h.on_event(SpeechStopped())
    assert h.state == IDLE
    h.on_event(Error(where="t", message="boom"))
    assert h.state == ERROR


def test_illegal_transitions_rejected():
    h = HUDStateMachine()
    h.on_event(UtteranceFinal(text="x"))  # no wake first
    assert h.state == IDLE
    h.on_event(ConfirmationAnswered(confirmed=True, tool="x"))  # nothing pending
    assert h.state == IDLE
    h.on_event(WakeDetected())
    h.on_event(SpeechStopped())  # not speaking
    assert h.state == LISTENING


def test_error_clears_on_wake():
    h = HUDStateMachine()
    h.on_event(WakeDetected())
    h.on_event(Error(where="stt", message="mic died"))
    assert h.state == ERROR
    assert h.error_info["where"] == "stt"
    h.on_event(WakeDetected())
    assert h.state == LISTENING
    assert h.error_info is None


def test_partial_upsert_then_commit():
    h = HUDStateMachine()
    h.on_event(UtterancePartial(text="hel"))
    h.on_event(UtterancePartial(text="hello"))
    assert len(h.transcript) == 1
    assert h.transcript[0].live is True
    assert h.transcript[0].text == "hello"
    h.on_event(UtteranceFinal(text="hello"))
    assert len(h.transcript) == 1
    assert h.transcript[0].live is False


def test_timeline_marks_finished():
    h = HUDStateMachine()
    h.on_event(ToolRequested(tool="open_application"))
    assert h.timeline[-1].ok is None
    h.on_event(ToolFinished(tool="open_application", ok=True))
    assert h.timeline[-1].label == "open_application ✓"
    h.on_event(ToolRequested(tool="web_search"))
    h.on_event(ToolFinished(tool="web_search", ok=False))
    assert h.timeline[-1].label == "web_search ✗"


def test_confirm_card_lifecycle():
    h = HUDStateMachine()
    h.on_event(WakeDetected())
    h.on_event(UtteranceFinal(text="do it"))
    h.on_event(ConfirmationRequested(tool="system_control", question="Sure?"))
    assert h.confirm_card == {"tool": "system_control", "question": "Sure?"}
    h.on_event(ConfirmationAnswered(confirmed=False, tool="system_control"))
    assert h.confirm_card is None
    assert h.state == THINKING


def test_audio_level_never_changes_state():
    h = HUDStateMachine()
    h.on_event({"type": "AudioLevel", "level": 0.9})
    assert h.state == IDLE
    assert h.audio_level == 0.9
    h.on_event({"type": "AudioLevel", "level": 99})  # clamped
    assert h.audio_level == 1.0


def test_subscriber_called_on_change():
    h = HUDStateMachine()
    seen = []
    h.subscribe(lambda kind, payload: seen.append(kind))
    h.on_event(WakeDetected())
    assert "state" in seen


def test_subscriber_failure_does_not_break_hud():
    h = HUDStateMachine()
    h.subscribe(lambda kind, payload: 1 / 0)
    h.on_event(WakeDetected())  # must not raise
    assert h.state == LISTENING


def test_snapshot_structure():
    h = HUDStateMachine()
    h.on_event(WakeDetected())
    h.on_event(UtteranceFinal(text="hi"))
    snap = h.snapshot()
    assert snap["state"] == THINKING
    assert isinstance(snap["transcript"], list)
    assert isinstance(snap["timeline"], list)
    assert "confirm_card" in snap and "error" in snap


def test_states_constant_matches_spec():
    assert set(STATES) == {"idle", "listening", "thinking", "speaking", "confirming", "error"}


# --- server routes ------------------------------------------------------


def _make_client(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from jarvis.server import api as api_mod

    monkeypatch.setattr(api_mod, "_FASTAPI_AVAILABLE", True)
    service = MagicMock()
    bus = MagicMock()
    service.bus = bus
    app = api_mod.create_app(service, token="test-token")
    # bus.on_all was called with hud.on_event during create_app
    assert bus.on_all.called
    return TestClient(app)


def test_hud_routes_require_auth(monkeypatch):
    c = _make_client(monkeypatch)
    assert c.get("/hud").status_code == 401
    assert c.get("/hud/index.html").status_code == 401
    assert c.get("/hud/snapshot").status_code == 401


def test_hud_serves_index_and_assets(monkeypatch):
    c = _make_client(monkeypatch)
    h = {"Authorization": "Bearer test-token"}
    r = c.get("/hud", headers=h)
    assert r.status_code == 200
    assert "JARVIS HUD" in r.text
    assert r.headers["content-type"].startswith("text/html")
    for name, ctype in [
        ("styles.css", "text/css"),
        ("app.js", "text/javascript"),
        ("control.html", "text/html"),
        ("manifest.json", "application/manifest+json"),
        ("sw.js", "text/javascript"),
    ]:
        r = c.get(f"/hud/{name}", headers=h)
        assert r.status_code == 200, name
        assert r.headers["content-type"].startswith(ctype), name


def test_hud_rejects_path_traversal(monkeypatch):
    c = _make_client(monkeypatch)
    h = {"Authorization": "Bearer test-token"}
    assert c.get("/hud/../api.py", headers=h).status_code in (404, 422)
    assert c.get("/hud/secret.txt", headers=h).status_code == 404


def test_hud_snapshot(monkeypatch):
    c = _make_client(monkeypatch)
    h = {"Authorization": "Bearer test-token"}
    r = c.get("/hud/snapshot", headers=h)
    assert r.status_code == 200
    snap = r.json()
    assert snap["state"] == "idle"
    assert "transcript" in snap and "timeline" in snap
