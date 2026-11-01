"""Tests for Task 1.6: mic safety.

Wake-word default, push-to-talk gating, mic-state indicator, Privacy Mode,
and the no-mic-data-on-disk guarantee.
"""

import sys
from unittest.mock import MagicMock, patch

for _mod in ("pyautogui",):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))

import pytest  # noqa: E402

from access_os.config import VoiceCfg, get_settings  # noqa: E402
from access_os.voice_interface import MicState, VoiceInterface  # noqa: E402


@pytest.fixture()
def voice(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = VoiceInterface.__new__(VoiceInterface)
    # Minimal init without touching hardware/TTS.
    v.config = {
        "wake_word": "jarvis",
        "require_wake_word": True,
        "privacy_mode": False,
        "push_to_talk": False,
        "push_to_talk_hotkey": "ctrl+alt+j",
        "max_utterance_s": 30.0,
    }
    v.wake_word = "jarvis"
    v.require_wake_word = True
    v.mic_state = MicState.IDLE
    v.privacy_mode = False
    v._mic_enabled = True
    v.push_to_talk = False
    v.push_to_talk_hotkey = "ctrl+alt+j"
    import threading
    v._ptt_held = threading.Event()
    v.is_listening = False
    v.microphone = None
    v._stop_event = threading.Event()
    v._listen_thread = None
    return v


# ---------------------------------------------------------------------------
# 1.6.1 wake word required by default
# ---------------------------------------------------------------------------

def test_wake_word_required_by_default():
    assert VoiceCfg().require_wake_word is True


def test_settings_default_require_wake_word(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VOICE__REQUIRE_WAKE_WORD", raising=False)
    from access_os.config import reset_settings_cache
    reset_settings_cache()
    try:
        assert get_settings().voice.require_wake_word is True
    finally:
        reset_settings_cache()


# ---------------------------------------------------------------------------
# 1.6.2 push-to-talk (default OFF)
# ---------------------------------------------------------------------------

def test_push_to_talk_defaults_off():
    cfg = VoiceCfg()
    assert cfg.push_to_talk is False
    assert cfg.push_to_talk_hotkey == "ctrl+alt+j"


def test_ptt_blocks_capture_until_held(voice):
    voice.push_to_talk = True
    allowed, _ = voice._capture_allowed()
    assert allowed is False
    assert voice.mic_state == MicState.IDLE
    voice.ptt_press()
    allowed, _ = voice._capture_allowed()
    assert allowed is True
    assert voice.mic_state == MicState.LISTENING
    voice.ptt_release()
    allowed, _ = voice._capture_allowed()
    assert allowed is False


def test_ptt_ignored_when_disabled(voice):
    voice.push_to_talk = False
    allowed, _ = voice._capture_allowed()
    assert allowed is True


# ---------------------------------------------------------------------------
# 1.6.3 mic state + Privacy Mode
# ---------------------------------------------------------------------------

def test_mic_states_exist():
    assert {s.name for s in MicState} == {
        "IDLE", "LISTENING", "PROCESSING", "MUTED", "PRIVACY"}


def test_mute_blocks_capture(voice):
    voice.set_mic_enabled(False)
    allowed, _ = voice._capture_allowed()
    assert allowed is False
    assert voice.mic_state == MicState.MUTED
    assert voice.mic_state_snapshot() == "MUTED"
    voice.set_mic_enabled(True)
    allowed, _ = voice._capture_allowed()
    assert allowed is True


def test_privacy_mode_blocks_capture_and_start(voice):
    with patch("access_os.config.save_legacy_voice_dict"):
        msg = voice.set_privacy_mode(True)
    assert voice.privacy_mode is True
    assert voice.mic_state == MicState.PRIVACY
    assert "Microphone is off" in msg
    allowed, _ = voice._capture_allowed()
    assert allowed is False
    # start_listening refuses while privacy is on
    voice.microphone = MagicMock()
    voice.start_listening()
    assert voice.is_listening is False
    with patch("access_os.config.save_legacy_voice_dict"):
        voice.set_privacy_mode(False)
    assert voice.privacy_mode is False


def test_privacy_mode_default_off():
    assert VoiceCfg().privacy_mode is False


# ---------------------------------------------------------------------------
# 1.6.4 no mic audio data is written to disk
# ---------------------------------------------------------------------------

def test_no_mic_audio_written_to_disk():
    """Static guarantee: the voice module never persists captured audio.

    Allowed: the TTS *output* temp wav (assistant's voice, deleted right
    after playback) — everything else that touches AudioData must be
    in-memory only.
    """
    import pathlib
    src = pathlib.Path("access_os/voice_interface.py").read_text(
        encoding="utf-8")
    # No persistence of recognizer audio: get_wav_data/get_raw_data must
    # never flow into open()/write().
    assert "get_wav_data" not in src
    assert "get_raw_data" not in src
    # The only audio file write is the TTS temp wav, which is removed
    # immediately after playback.
    assert src.count("JARVIS_rumik_") == 1
    assert "os.remove(temp_file)" in src
