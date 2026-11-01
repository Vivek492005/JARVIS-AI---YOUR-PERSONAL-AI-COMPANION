"""Tests for Task 3.2: wake-word engine."""

from __future__ import annotations

import sys
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, "src")

from jarvis.voice.wakeword import (  # noqa: E402
    DummyWakeBackend,
    WakeConfig,
    WakeWordEngine,
)


def _wake_frame(keyword="jarvis"):
    return b"WAKE:" + keyword.encode() + b"\x00" + bytes(300)


def test_dummy_backend_detects_configured_keyword():
    b = DummyWakeBackend()
    b.configure(["hey jarvis", "jarvis"], 0.5)
    assert b.process(_wake_frame("jarvis")) == "jarvis"
    assert b.process(_wake_frame("hey jarvis")) == "hey jarvis"
    assert b.process(_wake_frame("computer")) is None
    assert b.process(bytes(320)) is None


def test_engine_emits_and_cools_down():
    calls = []
    eng = WakeWordEngine(DummyWakeBackend(), on_wake=lambda kw, fu: calls.append((kw, fu)))
    assert eng.process(_wake_frame("jarvis")) == "jarvis"
    # within cooldown: suppressed
    assert eng.process(_wake_frame("jarvis")) is None
    assert calls == [("jarvis", False)]


def test_followup_window_flag():
    calls = []
    eng = WakeWordEngine(DummyWakeBackend(), on_wake=lambda kw, fu: calls.append((kw, fu)))
    eng.note_response()
    assert eng.in_followup_window()
    eng.process(_wake_frame("jarvis"))
    assert calls and calls[0][1] is True


def test_ducking_raises_effective_threshold():
    guard = MagicMock()
    guard.ducked = False
    eng = WakeWordEngine(DummyWakeBackend(), echo_guard=guard)
    assert eng._effective_threshold() == 0.5
    guard.ducked = True
    assert eng._effective_threshold() == 0.75


def test_backends_raise_helpful_errors_without_deps(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in ("openwakeword.model", "pvporcupine"):
            raise ImportError("nope")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from jarvis.voice.wakeword import OpenWakeWordBackend, PorcupineBackend
    try:
        OpenWakeWordBackend()
        raise AssertionError("should have raised")
    except RuntimeError as e:
        assert "pip install" in str(e)
    try:
        PorcupineBackend(access_key="x")
        raise AssertionError("should have raised")
    except RuntimeError as e:
        assert "pip install" in str(e)


def test_porcupine_needs_key():
    from jarvis.voice.wakeword import PorcupineBackend
    with pytest.raises(RuntimeError, match="access key"):
        PorcupineBackend(access_key="")
