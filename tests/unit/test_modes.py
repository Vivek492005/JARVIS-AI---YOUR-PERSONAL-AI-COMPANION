"""Tests for Task 3.9: input modes."""

from __future__ import annotations

import datetime
import sys

sys.path.insert(0, "src")

from jarvis.voice.modes import InputMode, InputModeManager, QuietHours  # noqa: E402


def _t(h, m=0):
    return datetime.time(h, m)


def test_quiet_hours_same_day_window():
    qh = QuietHours("23:00", "07:00")  # overnight
    assert qh.active(_t(23, 30))
    assert qh.active(_t(2, 0))
    assert not qh.active(_t(12, 0))
    assert not qh.active(_t(7, 0))  # end is exclusive


def test_quiet_hours_daytime_window():
    qh = QuietHours("13:00", "14:00")
    assert qh.active(_t(13, 30))
    assert not qh.active(_t(15, 0))


def test_quiet_hours_disabled():
    assert not QuietHours().active(_t(3, 0))


def test_mode_capture_policy():
    m = InputModeManager(InputMode.WAKEWORD)
    assert m.mic_captures()
    assert m.tts_allowed()
    assert m.requires_wake_word()

    m.set_mode(InputMode.TYPED)
    assert not m.mic_captures()
    assert m.tts_allowed()

    m.set_mode(InputMode.QUIET)
    assert m.mic_captures()       # mic on (whisper-level)
    assert not m.tts_allowed()    # replies text-only

    m.set_mode(InputMode.PTT)
    assert m.ptt_armed() and not m.requires_wake_word()


def test_quiet_hours_force_mic_off():
    m = InputModeManager(InputMode.WAKEWORD, QuietHours("23:00", "07:00"))
    assert m.mic_captures(now=_t(12, 0))
    assert not m.mic_captures(now=_t(2, 0))


def test_mode_change_callback():
    seen = []
    m = InputModeManager(on_change=lambda mode, reason: seen.append((mode, reason)))
    m.set_mode(InputMode.PTT, reason="voice command")
    assert seen == [(InputMode.PTT, "voice command")]
    m.set_mode(InputMode.PTT)  # no-op: no callback
    assert len(seen) == 1


def test_tick_quiet_hours_reports_changes():
    m = InputModeManager(InputMode.WAKEWORD, QuietHours("23:00", "07:00"))
    assert m.tick_quiet_hours(now=_t(12, 0)) is False
    assert m.tick_quiet_hours(now=_t(2, 0)) is True
    assert m.tick_quiet_hours(now=_t(3, 0)) is False  # no change
    assert m.tick_quiet_hours(now=_t(8, 0)) is True
