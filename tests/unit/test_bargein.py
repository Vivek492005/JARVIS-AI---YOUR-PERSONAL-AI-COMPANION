"""Tests for Task 3.7: barge-in."""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from jarvis.voice.bargein import BargeInConfig, BargeInController  # noqa: E402


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def _ctrl(**kw):
    clock = _Clock()
    calls = {"stop": 0, "interrupt": [], "llm": 0, "lane": 0}
    c = BargeInController(
        config=BargeInConfig(**kw.get("cfg", {})),
        stop_tts=lambda: calls.__setitem__("stop", calls["stop"] + 1),
        on_interrupt=lambda r: calls["interrupt"].append(r),
        on_cancel_llm=lambda: calls.__setitem__("llm", calls["llm"] + 1),
        on_cancel_lane=lambda: calls.__setitem__("lane", calls["lane"] + 1),
        clock=clock,
    )
    return c, clock, calls


def test_sustained_speech_fires_interrupt():
    c, clock, calls = _ctrl()
    c.note_tts_start()
    # 100 ms blips: no fire
    for _ in range(5):
        assert not c.feed_vad(True)
        clock.advance(0.02)
    # sustain past 300 ms
    for _ in range(15):
        clock.advance(0.02)
        fired = c.feed_vad(True)
        if fired:
            break
    assert fired
    assert calls["stop"] == 1
    assert calls["llm"] == 1 and calls["lane"] == 1
    assert len(calls["interrupt"]) == 1
    assert c.last_stop_latency_ms is not None


def test_blip_ignored_and_resets():
    c, clock, calls = _ctrl()
    c.note_tts_start()
    for _ in range(5):  # 100 ms
        c.feed_vad(True)
        clock.advance(0.02)
    c.feed_vad(False)  # silence resets the burst timer
    clock.advance(0.5)
    for _ in range(5):
        assert not c.feed_vad(True)
        clock.advance(0.02)
    assert calls["stop"] == 0


def test_no_fire_when_tts_not_playing():
    c, clock, calls = _ctrl()
    for _ in range(30):
        assert not c.feed_vad(True)
        clock.advance(0.02)
    assert calls["interrupt"] == []


def test_stop_word_hard_interrupt():
    c, clock, calls = _ctrl()
    c.note_tts_start()
    assert c.check_partial("ruko")
    assert calls["stop"] == 1
    assert "stop word" in calls["interrupt"][0]


def test_stop_word_ignored_when_idle():
    c, clock, calls = _ctrl()
    assert not c.check_partial("bas")
    assert calls["stop"] == 0


def test_ducked_requires_longer_burst():
    c, clock, calls = _ctrl()
    c.note_tts_start()
    c.ducked = True  # 300 ms * 2 = 600 ms required
    fired = False
    for _ in range(20):  # 400 ms
        clock.advance(0.02)
        fired = c.feed_vad(True)
    assert not fired
    for _ in range(15):  # +300 ms = 700 ms total
        clock.advance(0.02)
        fired = c.feed_vad(True)
        if fired:
            break
    assert fired


def test_disabled_controller_never_fires():
    c, clock, calls = _ctrl(cfg={"enabled": False})
    c.note_tts_start()
    for _ in range(50):
        assert not c.feed_vad(True)
        clock.advance(0.02)
    assert calls["stop"] == 0


def test_context_note():
    assert "beech mein roka" in BargeInController.context_note()
