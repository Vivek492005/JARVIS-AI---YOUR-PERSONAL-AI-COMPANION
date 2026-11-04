"""Tests for Task 3.1: audio capture, ring buffer, echo guard."""

from __future__ import annotations

import sys
import time

import pytest

sys.path.insert(0, "src")

from jarvis.voice.audio import (  # noqa: E402
    AudioCapture,
    EchoGuard,
    RingBuffer,
    check_audio,
    list_input_devices,
)


class _ScriptedSource:
    """AudioSource yielding scripted frames then None."""

    def __init__(self, frames, sample_rate=16000):
        self._frames = list(frames)
        self._sample_rate = sample_rate
        self.closed = False

    @property
    def sample_rate(self):
        return self._sample_rate

    def read_frame(self):
        if not self._frames:
            time.sleep(0.01)
            return None
        return self._frames.pop(0)

    def close(self):
        self.closed = True


def _frame(n=320):
    return bytes(n)  # 20 ms of silence at 16kHz mono 16-bit


def test_ring_buffer_preroll_drain():
    rb = RingBuffer(sample_rate=16000, capacity_s=0.1, frame_ms=20)  # 5 frames
    for _ in range(10):
        rb.push(_frame())
    assert len(rb) == 5  # capped
    data = rb.drain_preroll()
    assert len(data) == 5 * 320
    assert len(rb) == 0  # drained


def test_capture_preroll_available_before_vad_fires():
    src = _ScriptedSource([_frame()] * 200)
    cap = AudioCapture(src, frame_ms=20, preroll_s=1.5)
    cap.start()
    time.sleep(0.3)  # let the pump run
    preroll = cap.drain_preroll()
    cap.stop()
    # 1.5 s at 20 ms frames = 75 frames of 320 bytes
    assert len(preroll) == 75 * 320
    assert src.closed


def test_capture_on_frame_callback():
    seen = []
    src = _ScriptedSource([_frame()] * 5)
    cap = AudioCapture(src, on_frame=seen.append)
    cap.start()
    cap._thread.join(timeout=2.0)
    cap.stop()
    assert len(seen) == 5


def test_echo_guard_ducking():
    g = EchoGuard("ducking")
    assert not g.ducked
    g.tts_active = True
    assert g.ducked
    g.tts_active = False
    assert not g.ducked


def test_echo_guard_headset_never_ducks():
    g = EchoGuard("headset")
    g.tts_active = True
    assert not g.ducked


def test_echo_guard_invalid_mode():
    with pytest.raises(ValueError):
        EchoGuard("magic")


def test_echo_guard_webrtc_needs_backend():
    g = EchoGuard("webrtc")
    with pytest.raises(RuntimeError, match="no AEC backend"):
        g.process(b"\x00" * 320)
    g.register_aec_backend(lambda mic, ref: b"\x01" * 320)
    assert g.process(b"\x00" * 320) == b"\x01" * 320


def test_echo_guard_passthrough_by_default():
    g = EchoGuard("ducking")
    frame = b"\x02" * 320
    assert g.process(frame) is frame


def test_list_devices_without_sounddevice(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sounddevice":
            raise ImportError("nope")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert list_input_devices() == []


def test_check_audio_reports_missing_sounddevice(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sounddevice":
            raise ImportError("nope")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    chk = check_audio()
    assert not chk.ok and "sounddevice" in chk.detail
