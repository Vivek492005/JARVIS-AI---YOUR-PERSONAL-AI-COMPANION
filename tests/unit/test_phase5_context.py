"""Tests for Phase 5.8 context awareness (privacy-safe)."""

import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, "tests")

from jarvis.perception.context import format_snapshot, get_context  # noqa: E402
from jarvis.tools.registry import REGISTRY, Risk  # noqa: E402
from fakes.fake_desktop import install_fake_desktop, uninstall_fake_desktop  # noqa: E402


@pytest.fixture()
def desktop():
    made = install_fake_desktop()
    yield made
    uninstall_fake_desktop()


def test_basic_snapshot_presence_flags(desktop):
    made = desktop
    made["context"] = _ctx(selection="hello", clipboard=True)
    _reinstall(made)
    snap = get_context()
    assert snap.window_title == "Untitled - Notepad"
    assert snap.has_selection is True
    assert snap.has_clipboard_text is True
    # content NOT included by default
    assert snap.selection_text == ""
    assert snap.clipboard_text == ""


def test_selection_content_on_explicit_ask(desktop):
    made = desktop
    made["context"] = _ctx(selection="Error 0x80070005", clipboard=False)
    _reinstall(made)
    snap = get_context(detail="selection")
    assert "0x80070005" in snap.selection_text


def test_clipboard_content_on_explicit_ask(desktop):
    made = desktop
    made["context"] = _ctx(clipboard=True, clipboard_text="secret-token abc")
    _reinstall(made)
    snap = get_context(detail="clipboard")
    assert "secret-token" in snap.clipboard_text


def test_sensitive_window_redacted(desktop):
    made = desktop
    made["context"] = _ctx(title="KeePassXC", process="keepassxc.exe", selection="hunter2")
    _reinstall(made)
    snap = get_context(detail="selection")
    assert snap.window_title == "[sensitive window]"
    assert snap.selection_text == ""  # never leak from sensitive windows


def test_selection_redacted(desktop):
    made = desktop
    made["context"] = _ctx(selection="card 4111 1111 1111 1111")
    _reinstall(made)
    snap = get_context(detail="selection")
    assert "4111" not in snap.selection_text
    assert "[REDACTED]" in snap.selection_text


def test_toggle_off_returns_minimal(desktop, monkeypatch):
    import jarvis.perception.context as ctx_mod

    monkeypatch.setattr(ctx_mod, "_enabled", lambda: False)
    snap = get_context()
    assert snap.window_title == ""
    assert snap.has_selection is False


def test_format_snapshot(desktop):
    made = desktop
    made["context"] = _ctx(selection="x")
    _reinstall(made)
    out = format_snapshot(get_context(detail="selection"))
    assert "active window: Untitled - Notepad" in out
    assert "selection: yes" in out
    assert "selected text: x" in out


def test_tool_registered():
    assert REGISTRY["get_context"].risk == Risk.READ
    assert REGISTRY["get_context"].carries_external_data is True


def test_run_action_get_context(desktop):
    from jarvis.tools.actions import run_action

    verdict, result = run_action("get_context", {})
    assert verdict == "allow", result
    assert "active window" in result
    verdict, result = run_action("get_context", {"detail": "bogus"})
    assert "unknown detail" in result


# -- helpers ---------------------------------------------------------------


def _ctx(**kw):
    from fakes.fake_desktop import FakeContext

    return FakeContext(**kw)


def _reinstall(made):
    from jarvis.perception import backends as B

    B.set_backend("context", made["context"])
