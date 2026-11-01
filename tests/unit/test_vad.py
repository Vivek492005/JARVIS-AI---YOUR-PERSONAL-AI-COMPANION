"""Tests for Task 3.3: VAD + end-of-turn endpointing."""

from __future__ import annotations

import math
import struct
import sys

sys.path.insert(0, "src")

from jarvis.voice.vad import (  # noqa: E402
    CONNECTOR_WORDS,
    Endpointer,
    EndpointConfig,
    EnergyVAD,
    _rms_db,
)


def _tone_frame(ms=20, freq=440.0, amp=16000, sr=16000):
    n = int(sr * ms / 1000)
    return struct.pack(
        f"<{n}h",
        *[int(amp * math.sin(2 * math.pi * freq * i / sr)) for i in range(n)],
    )


def _silence_frame(ms=20, sr=16000):
    return bytes(int(sr * ms / 1000) * 2)


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def test_energy_vad_detects_tone_vs_silence():
    vad = EnergyVAD()
    # Let the floor settle on silence first.
    for _ in range(50):
        assert not vad.is_speech(_silence_frame())
    assert vad.is_speech(_tone_frame())
    # Floor adapted downward on silence.
    assert vad.floor_db < -50.0


def test_endpointer_completes_turn_after_hangover():
    clock = _Clock()
    ep = Endpointer(EnergyVAD(), EndpointConfig(hangover_ms=500), clock=clock)
    # Warm up the VAD floor.
    for _ in range(30):
        ep.feed(_silence_frame())
    # Speech for 1 s.
    for _ in range(50):
        assert ep.feed(_tone_frame())
        clock.advance(0.02)
    # Silence: hangover 500 ms -> still open at 400 ms, done at 600 ms.
    for _ in range(20):
        assert ep.feed(_silence_frame())
        clock.advance(0.02)
    assert ep.feed(_silence_frame())  # 400 ms silence: open
    clock.advance(0.02)
    for _ in range(9):
        ep.feed(_silence_frame())
        clock.advance(0.02)
    assert not ep.feed(_silence_frame())  # ~600 ms: closed
    audio, dur = ep.take_utterance()
    assert len(audio) == 50 * 640  # 20 ms frames = 320 samples x 2 bytes
    assert 0.9 < dur < 1.1


def test_connector_word_extends_hangover():
    clock = _Clock()
    cfg = EndpointConfig(hangover_ms=500, hangover_extension_ms=400)
    ep = Endpointer(EnergyVAD(), cfg, clock=clock)
    for _ in range(30):
        ep.feed(_silence_frame())
    for _ in range(25):
        ep.feed(_tone_frame())
        clock.advance(0.02)
    ep.partial_transcript = "chrome khol aur"
    assert "aur" in CONNECTOR_WORDS
    # 500 ms silence would normally close; connector extends to 900 ms.
    for _ in range(25):
        assert ep.feed(_silence_frame())
        clock.advance(0.02)
    # Still open at 500 ms thanks to the extension...
    assert ep.feed(_silence_frame())
    clock.advance(0.02)
    for _ in range(19):
        ep.feed(_silence_frame())
        clock.advance(0.02)
    assert not ep.feed(_silence_frame())  # ~900 ms: closed


def test_max_utterance_cap():
    clock = _Clock()
    cfg = EndpointConfig(max_utterance_s=1.0)
    ep = Endpointer(EnergyVAD(), cfg, clock=clock)
    for _ in range(30):
        ep.feed(_silence_frame())
    open_state = True
    for _ in range(100):
        open_state = ep.feed(_tone_frame())
        clock.advance(0.02)
        if not open_state:
            break
    assert not open_state  # capped at 1 s, not waiting for silence


def test_blip_ignored():
    clock = _Clock()
    cfg = EndpointConfig(min_utterance_ms=200)
    ep = Endpointer(EnergyVAD(), cfg, clock=clock)
    for _ in range(30):
        ep.feed(_silence_frame())
    for _ in range(3):  # 60 ms blip
        ep.feed(_tone_frame())
        clock.advance(0.02)
    for _ in range(40):
        ep.feed(_silence_frame())
        clock.advance(0.02)
    assert ep.take_utterance() is None  # too short: discarded


def test_webrtc_backend_helpful_error(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "webrtcvad":
            raise ImportError("nope")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from jarvis.voice.vad import WebRTCVADBackend
    try:
        WebRTCVADBackend()
        raise AssertionError("should raise")
    except RuntimeError as e:
        assert "pip install" in str(e)
