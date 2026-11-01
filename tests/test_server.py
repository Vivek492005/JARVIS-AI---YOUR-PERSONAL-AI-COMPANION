"""Tests for Task 2.4: jarvisd service/client split."""

import os
import stat
import time

import pytest

from jarvis.core.events import StatusChanged, reset_bus
from jarvis.server.client import HttpJarvisClient, JarvisClient
from jarvis.server.service import JarvisService
from jarvis.server.token import bearer_ok, get_or_create_token


@pytest.fixture()
def service():
    reset_bus()
    svc = JarvisService(handler=lambda text, token, svc: f"echo:{text}")
    svc.start()
    yield svc
    svc.stop()
    reset_bus()


def _wait_for(pred, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.01)
    return False


def test_service_submit_and_handler(service):
    tok = service.submit_command("hello")
    # handler result flows through the lane; poll state instead
    assert _wait_for(lambda: service.commands_processed == 1)
    assert service.get_state()["commands_processed"] == 1
    assert tok is not None


def test_service_handler_result_reaches_caller(service):

    def handler(text, token, svc):
        return f"did:{text}"

    service.handler = handler
    done = []
    service.lanes.submit(lambda tok: done.append(service._run_command("x", tok)),
                         name="t")
    assert _wait_for(lambda: done)
    assert done[0] == "did:x"


def test_service_rejects_empty_command(service):
    with pytest.raises(ValueError):
        service.submit_command("   ")


def test_service_state_shape(service):
    st = service.get_state()
    assert st["v"] == 1
    assert st["running"] is True
    assert st["queue_depth"] >= 0
    assert "version" in st


def test_client_send_and_state(service):
    client = JarvisClient(service)
    client.send_command("hi")
    assert _wait_for(lambda: service.commands_processed == 1)
    assert client.get_state()["commands_processed"] == 1


def test_client_subscribe_receives_events(service):
    client = JarvisClient(service)
    seen = []
    client.subscribe(StatusChanged, seen.append)
    service.bus.emit(StatusChanged(status="hello"))
    assert len(seen) == 1
    assert seen[0].status == "hello"


def test_client_interrupt(service):
    client = JarvisClient(service)
    gate = __import__("threading").Event()
    service.handler = lambda text, token, svc: gate.wait(5) or "x"
    service.submit_command("long")
    time.sleep(0.1)
    client.interrupt("test")
    # interrupt is cooperative; the handler doesn't check the token, but the
    # call itself must not raise and the lane must stay alive.
    assert service.running


def test_send_text_command_alias_blank(service):
    client = JarvisClient(service)
    assert client.send_text_command("   ") is None
    assert client.send_text_command("hi") is not None


# -- token ---------------------------------------------------------------

def test_token_created_once_with_0600(tmp_path):
    p = tmp_path / "token"
    t1 = get_or_create_token(p)
    t2 = get_or_create_token(p)
    assert t1 == t2
    assert len(t1) == 64
    mode = stat.S_IMODE(os.stat(p).st_mode)
    assert mode == 0o600


def test_bearer_ok():
    assert bearer_ok("Bearer abc123", "abc123")
    assert bearer_ok("bearer abc123", "abc123")
    assert not bearer_ok("Bearer wrong", "abc123")
    assert not bearer_ok(None, "abc123")
    assert not bearer_ok("Token abc123", "abc123")


# -- HTTP API (needs the server extra) ------------------------------------

fastapi = pytest.importorskip("fastapi")


def test_api_health_state_command():
    from fastapi.testclient import TestClient
    from jarvis.server.api import create_app

    reset_bus()
    svc = JarvisService(handler=lambda text, token, svc: f"echo:{text}")
    svc.start()
    try:
        token = "test-token-123"
        app = create_app(svc, token)
        c = TestClient(app)

        r = c.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        # no token -> 401
        assert c.get("/state").status_code == 401
        assert c.post("/command", json={"text": "hi"}).status_code == 401

        h = {"Authorization": "Bearer test-token-123"}
        st = c.get("/state", headers=h)
        assert st.status_code == 200
        assert st.json()["v"] == 1

        r = c.post("/command", json={"text": "hello", "priority": "TASK"}, headers=h)
        assert r.json() == {"v": 1, "accepted": True}
        assert _wait_for(lambda: svc.commands_processed == 1)

        # bad priority / empty -> 400
        assert c.post("/command", json={"text": "x", "priority": "NOPE"},
                      headers=h).status_code == 400
        assert c.post("/command", json={"text": "  "}, headers=h).status_code == 400
    finally:
        svc.stop()
        reset_bus()


def test_api_websocket_events_and_auth():
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from jarvis.core.events import StatusChanged
    from jarvis.server.api import create_app

    reset_bus()
    svc = JarvisService(handler=lambda text, token, svc: "ok")
    svc.start()
    try:
        app = create_app(svc, "tok-xyz")
        c = TestClient(app)
        # wrong token -> closed
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect("/events?token=nope"):
                pass
        # right token -> hello + event stream
        with c.websocket_connect("/events?token=tok-xyz") as ws:
            hello = ws.receive_json()
            assert hello["type"] == "hello"
            svc.bus.emit(StatusChanged(status="ping"))
            msg = ws.receive_json()
            assert msg["type"] == "StatusChanged"
            assert msg["status"] == "ping"
            assert msg["v"] == 1
    finally:
        svc.stop()
        reset_bus()


def test_http_client_against_api():
    import httpx

    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        seen["path"] = request.url.path
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"v": 1, "accepted": True})

    client = HttpJarvisClient.__new__(HttpJarvisClient)
    client._http = httpx.Client(transport=httpx.MockTransport(handler),
                                base_url="http://127.0.0.1:8765",
                                headers={"Authorization": "Bearer tok-abc"})
    out = client.send_command("hello", priority="TASK")
    assert out == {"v": 1, "accepted": True}
    assert seen["auth"] == "Bearer tok-abc"
    assert seen["path"] == "/command"
    assert "TASK" in seen["body"]
    client.close()
