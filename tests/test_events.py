"""Tests for Task 2.2: event bus (jarvis.core.events)."""

import asyncio
import sys
import threading
import time
from unittest.mock import MagicMock

import pytest

from jarvis.core.events import (
    AgentThinking,
    Bus,
    Error,
    Event,
    Interrupt,
    SpeechStarted,
    SpeechStopped,
    StatusChanged,
    ToolFinished,
    ToolRequested,
    UtteranceFinal,
    get_bus,
    new_trace,
    reset_bus,
)


def test_event_defaults():
    ev = UtteranceFinal(text="hello")
    assert ev.trace == ""
    assert ev.ts > 0
    assert ev.text == "hello"
    assert ev.lang == "hi-en"


def test_new_trace_unique():
    assert new_trace() != new_trace()
    assert len(new_trace()) == 12


def test_emit_dispatches_to_subscribers():
    bus = Bus()
    seen = []
    bus.on(UtteranceFinal, seen.append)
    bus.emit(UtteranceFinal(text="hi", trace="t1"))
    assert len(seen) == 1
    assert seen[0].text == "hi"
    assert seen[0].trace == "t1"


def test_emit_only_matching_type():
    bus = Bus()
    seen = []
    bus.on(UtteranceFinal, seen.append)
    bus.emit(StatusChanged(status="x"))
    assert seen == []


def test_crashing_subscriber_does_not_break_others():
    bus = Bus()
    seen = []

    def bad(ev):
        raise RuntimeError("boom")

    bus.on(Error, bad)
    bus.on(Error, seen.append)
    bus.emit(Error(where="test", message="m"))  # must not raise
    assert len(seen) == 1


def test_off_unsubscribes():
    bus = Bus()
    seen = []
    bus.on(Interrupt, seen.append)
    bus.off(Interrupt, seen.append)
    bus.emit(Interrupt(reason="x"))
    assert seen == []


def test_on_returns_handler_for_decorator_use():
    bus = Bus()
    seen = []

    def handler(ev):
        pass

    assert bus.on(ToolRequested, handler) is handler
    bus.on(ToolRequested, seen.append)
    bus.emit(ToolRequested(tool="t"))
    assert len(seen) == 1


def test_async_subscriber_skipped_without_loop(caplog):
    bus = Bus()
    called = []

    async def ahandler(ev):
        called.append(ev)

    bus.on(SpeechStarted, ahandler)
    with caplog.at_level("DEBUG", logger="jarvis.core.events"):
        bus.emit(SpeechStarted(text="hi"))
    assert called == []


def test_async_subscriber_scheduled_with_loop():
    bus = Bus()
    called = []

    async def ahandler(ev):
        called.append(ev)

    bus.on(SpeechStarted, ahandler)
    loop = asyncio.new_event_loop()

    async def runner():
        bus.attach_loop(asyncio.get_running_loop())
        bus.emit(SpeechStarted(text="hi"))
        await asyncio.sleep(0.1)

    try:
        loop.run_until_complete(runner())
    finally:
        loop.close()
    assert len(called) == 1
    assert called[0].text == "hi"


def test_aemit_awaits_coroutine_subscribers():
    async def main():
        bus = Bus()
        order = []

        async def ahandler(ev):
            await asyncio.sleep(0)
            order.append("async")

        def shandler(ev):
            order.append("sync")

        bus.on(ToolFinished, ahandler)
        bus.on(ToolFinished, shandler)
        await bus.aemit(ToolFinished(tool="t"))
        assert order == ["async", "sync"]

    asyncio.run(main())


def test_emit_thread_safe():
    bus = Bus()
    count = [0]
    lock = threading.Lock()

    def handler(ev):
        with lock:
            count[0] += 1

    bus.on(StatusChanged, handler)
    threads = [threading.Thread(target=bus.emit, args=(StatusChanged(status="s"),))
               for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert count[0] == 20


def test_default_bus_singleton_and_reset():
    b1 = get_bus()
    b2 = get_bus()
    assert b1 is b2
    b3 = reset_bus()
    assert b3 is not b1
    assert get_bus() is b3
    reset_bus()  # leave clean for other tests


def test_speak_emits_speech_events():
    """VoiceInterface.speak publishes SpeechStarted/Stopped (F-14 wiring)."""
    for _mod in ("pyautogui", "pyperclip", "speech_recognition", "pyttsx3",
                 "fuzzywuzzy", "fuzzywuzzy.fuzz"):
        sys.modules.setdefault(_mod, MagicMock(name=_mod))
    from jarvis.voice.interface import VoiceInterface

    bus = reset_bus()
    started, stopped = [], []
    bus.on(SpeechStarted, started.append)
    bus.on(SpeechStopped, stopped.append)

    vi = VoiceInterface.__new__(VoiceInterface)
    vi.bus = bus
    vi._tts_lock = threading.Lock()
    vi.config = {"tts_engine": "none"}
    vi.engine = None
    vi._privacy_tts_only_local = lambda: False
    vi.speak("hello world", wait=True)

    assert len(started) == 1
    assert started[0].text == "hello world"
    assert len(stopped) == 1
    reset_bus()


def test_agent_dispatch_emits_tool_events():
    """AIAgent._dispatch_tool_call publishes ToolRequested/ToolFinished."""
    from jarvis.brain.agent import AIAgent

    bus = reset_bus()
    requested, finished = [], []
    bus.on(ToolRequested, requested.append)
    bus.on(ToolFinished, finished.append)

    agent = AIAgent.__new__(AIAgent)
    agent.bus = bus
    agent.session_id = "test-trace"
    agent.rate_limited = False
    agent.tainted = False
    from jarvis.core.safety import RateLimiter, CircuitBreaker
    agent._rate_limiter = RateLimiter(max_calls=1000)
    agent._breaker = CircuitBreaker()
    agent._audit = lambda *a, **k: None
    agent._execute_tool = lambda name, args: "done-ok"

    out = agent._dispatch_tool_call("web_search", {"query": "x"})
    assert out == "done-ok"
    assert len(requested) == 1
    assert requested[0].tool == "web_search"
    assert requested[0].args == {"query": "x"}
    assert len(finished) == 1
    assert finished[0].ok is True
    assert finished[0].tool == "web_search"
    reset_bus()


def test_main_py_has_no_speak_monkeypatch():
    """F-14 done-when: no `self.voice.speak = ...` in main.py."""
    import pathlib
    src = pathlib.Path("main.py").read_text(encoding="utf-8")
    assert "self.voice.speak =" not in src
    assert "_orig_speak" not in src
    assert "SpeechStarted" in src  # GUI subscribes instead
