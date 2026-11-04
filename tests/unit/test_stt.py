"""Tests for Tasks 3.4/3.5: STT engines, WER, streaming partials."""

from __future__ import annotations

import sys

sys.path.insert(0, "src")
sys.path.insert(0, "tests/fakes")

import pytest  # noqa: E402

from jarvis.voice.stt import (  # noqa: E402
    Transcription,
    list_engines,
    make_engine,
)
from evals.stt.stt_bakeoff import wer  # noqa: E402
from fake_streaming_stt import FakeStreamingSTT  # noqa: E402


def test_engine_registry():
    engines = list_engines()
    assert {"google", "faster-whisper", "sarvam", "deepgram", "scribe"} <= set(engines)
    assert make_engine("google").name == "google"
    assert make_engine("faster-whisper:medium").name == "faster-whisper:medium"
    with pytest.raises(ValueError):
        make_engine("nope")


def test_wer_perfect_and_empty():
    assert wer("chrome khol", "chrome khol") == 0.0
    assert wer("chrome khol", "firefox khol") == 0.5
    assert wer("", "") == 0.0


def test_batch_fallback_streaming_yields_single_final():
    from jarvis.voice.stt import GoogleSTTEngine

    eng = GoogleSTTEngine()
    assert not eng.supports_streaming
    # Don't hit the network: stub transcribe.
    eng.transcribe = lambda audio, language="hi-en", sample_rate=16000: Transcription(
        text="hello", engine="google"
    )
    outs = list(eng.stream([b"\x00" * 320] * 5))
    assert len(outs) == 1 and outs[0].is_final and outs[0].text == "hello"


def test_fake_streaming_partials_then_final():
    eng = FakeStreamingSTT(partials=["chr", "chrome", "chrome kh"], final="chrome khol")
    outs = list(eng.stream([b"\x00" * 320] * 10))
    partials = [o for o in outs if not o.is_final]
    finals = [o for o in outs if o.is_final]
    assert len(finals) == 1 and finals[0].text == "chrome khol"
    assert [p.text for p in partials] == ["chr", "chrome", "chrome kh"]
    # Partials grow monotonically (prefix property).
    for a, b in zip(partials, partials[1:], strict=False):
        assert b.text.startswith(a.text)


def test_cloud_engines_need_keys():
    from jarvis.voice.stt import SarvamEngine, DeepgramEngine, ScribeEngine

    for cls, key in [
        (SarvamEngine, "SARVAM_API_KEY"),
        (DeepgramEngine, "DEEPGRAM_API_KEY"),
        (ScribeEngine, "ELEVENLABS_API_KEY"),
    ]:
        eng = cls(api_key="")
        with pytest.raises(RuntimeError, match=key):
            eng.transcribe(b"\x00" * 320)


def test_lazy_engines_raise_helpful_errors(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in ("faster_whisper", "speech_recognition"):
            raise ImportError("nope")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from jarvis.voice.stt import FasterWhisperEngine

    with pytest.raises(RuntimeError, match="pip install"):
        FasterWhisperEngine().transcribe(b"\x00" * 320)
