"""Tests for Task 3.6: streaming TTS, chunking, Hinglish voices, XTTS."""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from jarvis.voice.tts import (  # noqa: E402
    AudioChunk,
    PhraseCache,
    SentenceSplitter,
    StreamingTTS,
    detect_script,
    speak_style,
)


def test_sentence_splitter_incremental():
    sp = SentenceSplitter()
    out = []
    for tok in ["Hello ", "world. ", "Kaise ", "ho? ", "trailing"]:
        out.extend(sp.feed(tok))
    assert out == ["Hello world.", "Kaise ho?"]
    assert sp.flush() == ["trailing"]


def test_sentence_splitter_hindi_danda():
    sp = SentenceSplitter()
    assert sp.feed("Namaste। ") == ["Namaste।"]


def test_detect_script():
    assert detect_script("chrome khol de") == "en"      # Latin Hinglish -> en voice
    assert detect_script("क्रोम खोल दे") == "hi"          # Devanagari -> hi voice
    assert detect_script("") == "en"
    assert detect_script("123") == "en"


def test_speak_style_caps_sentences_and_strips_urls():
    text = ("Chrome khol diya. Ab kya karna hai? Yeh raha link https://example.com/x. "
            "Aur ek teesra sentence jo nahi bolna chahiye.")
    out = speak_style(text)
    assert "https://" not in out
    assert out.count(".") + out.count("?") <= 2
    assert "teesra" not in out


def test_speak_style_strips_code():
    out = speak_style("Result: ```print('hi')``` done.")
    assert "print" not in out and "done" in out


class _FakeTTS:
    name = "fake-tts"
    offline_capable = True

    def __init__(self):
        self.calls = []

    def synth(self, text, voice=None):
        self.calls.append((text, voice))
        return b"AUDIO:" + text.encode()

    def synth_stream(self, sentences, voice=None):
        for i, s in enumerate(sentences):
            yield AudioChunk(data=self.synth(s, voice), index=i, text=s, engine=self.name)


def test_streaming_tts_emits_per_sentence_in_order():
    prov = _FakeTTS()
    got = []
    st = StreamingTTS(prov, on_audio=got.append)
    st.speak_stream(iter(["Hello world. ", "Kaise ho? ", "Bye"]))
    assert [c.text for c in got] == ["Hello world.", "Kaise ho?", "Bye"]
    assert [c.index for c in got] == [0, 1, 2]
    assert st.first_audio_latency_s is not None and st.first_audio_latency_s >= 0


def test_streaming_tts_stop():
    prov = _FakeTTS()
    got = []
    st = StreamingTTS(prov, on_audio=got.append)
    st.stop()  # stopped before starting: emits nothing
    st.speak_stream(iter(["Hello. ", "World. "]))
    assert got == []


def test_streaming_tts_skips_failed_sentence():
    class Flaky(_FakeTTS):
        def synth(self, text, voice=None):
            if "bad" in text:
                raise RuntimeError("boom")
            return super().synth(text, voice)

    prov = Flaky()
    got = []
    StreamingTTS(prov, on_audio=got.append).speak_stream(iter(["Good. ", "bad. ", "Also good. "]))
    assert [c.text for c in got] == ["Good.", "Also good."]


def test_phrase_cache_synths_once():
    prov = _FakeTTS()
    cache = PhraseCache(prov)
    a = cache.get("Done")
    b = cache.get("Done")
    assert a == b == b"AUDIO:Done"
    assert len(prov.calls) == 1


def test_xtts_lazy_error_without_package(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "TTS.api":
            raise ImportError("nope")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from jarvis.voice.tts_xtts import XTTSEngine, check_xtts
    eng = XTTSEngine()
    assert eng.offline_capable
    try:
        eng.synth("hello")
        raise AssertionError("should raise")
    except RuntimeError as e:
        assert "pip install jarvis-assistant[xtts]" in str(e)
    ok, detail = check_xtts()
    assert not ok and "not installed" in detail


def test_xtts_needs_speaker_wav(tmp_path, monkeypatch):
    import builtins
    real_import = builtins.__import__
    fake_tts_mod = type("FakeTTSMod", (), {})()

    class FakeTTS:
        def __init__(self, *a, **k):
            pass

        def to(self, device):
            return self

        def tts_to_file(self, **kwargs):
            raise AssertionError("must not reach synth without speaker wav")

    fake_tts_mod.TTS = FakeTTS

    def fake_import(name, *args, **kwargs):
        if name == "TTS.api":
            return fake_tts_mod
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from jarvis.voice.tts_xtts import XTTSEngine
    eng = XTTSEngine(speaker_wav="/nonexistent/voice.wav")
    try:
        eng.synth("hello")
        raise AssertionError("should raise")
    except RuntimeError as e:
        assert "speaker reference WAV" in str(e)
