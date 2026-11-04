"""Tests for Task 1.10: privacy egress table + Privacy Mode wiring."""

import sys
from unittest import mock
from unittest.mock import MagicMock

for _mod in ("speech_recognition", "pyttsx3", "pyautogui", "pyperclip", "fuzzywuzzy"):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))
sys.modules["fuzzywuzzy"].fuzz = MagicMock()

import pytest  # noqa: E402

from access_os.config import PrivacyCfg, reset_settings_cache  # noqa: E402


def _fresh_settings(tmp_path, monkeypatch, **env):
    monkeypatch.chdir(tmp_path)
    for k in (
        "PRIVACY__PRIVACY_MODE",
        "PRIVACY__ALLOW_HUGGINGFACE",
        "PRIVACY__ALLOW_DEEPSEEK",
        "PRIVACY__ALLOW_RUMIK_TTS",
        "PRIVACY__ALLOW_GOOGLE_STT",
    ):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    reset_settings_cache()
    from access_os.config import get_settings

    try:
        return get_settings()
    finally:
        pass


@pytest.fixture()
def clean(tmp_path, monkeypatch):
    s = _fresh_settings(tmp_path, monkeypatch)
    yield s
    reset_settings_cache()


def test_privacy_defaults():
    p = PrivacyCfg()
    assert p.privacy_mode is False
    assert p.allow_huggingface is True
    assert p.allow_deepseek is True
    assert p.allow_rumik_tts is True
    assert p.allow_google_stt is True


def test_egress_toggle_blocks_client_creation(clean, tmp_path, monkeypatch):
    monkeypatch.setenv("PRIVACY__ALLOW_HUGGINGFACE", "false")
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "k")
    reset_settings_cache()
    from access_os.ai_agent import AIAgent

    a = AIAgent.__new__(AIAgent)
    a.hf_api_key = "k"
    a.ds_api_key = ""
    a.hf_base_url = "http://x"
    a.ds_base_url = "http://x"
    a.hf_model = "m"
    a.client = "sentinel"
    a.backup_client = "sentinel"
    with mock.patch("openai.OpenAI", create=True) as m:
        AIAgent._init_clients(a)
    m.assert_not_called()
    assert a.client == "sentinel"  # untouched


def test_privacy_mode_skips_cloud(clean, tmp_path, monkeypatch):
    monkeypatch.setenv("PRIVACY__PRIVACY_MODE", "true")
    reset_settings_cache()
    from access_os.ai_agent import AIAgent

    a = AIAgent.__new__(AIAgent)
    a.tainted = False
    a.pending_confirmation = None
    a.client = MagicMock()
    a.backup_client = None
    a._notify_status = lambda m: None
    with mock.patch.object(AIAgent, "_local_fallback_process", return_value="local") as m:
        resp = AIAgent.process(a, "hello")
    m.assert_called_once()
    a.client.chat.completions.create.assert_not_called()
    assert resp == "local"


def test_egress_denied_under_privacy_mode(clean, tmp_path, monkeypatch):
    monkeypatch.setenv("PRIVACY__PRIVACY_MODE", "true")
    reset_settings_cache()
    from access_os.ai_agent import AIAgent

    a = AIAgent.__new__(AIAgent)
    assert AIAgent._privacy_on(a) is True
    assert AIAgent._egress(a, "huggingface") is False
    assert AIAgent._egress(a, "deepseek") is False


def test_tts_local_only_under_privacy(clean, tmp_path, monkeypatch):
    monkeypatch.setenv("PRIVACY__PRIVACY_MODE", "true")
    reset_settings_cache()
    from access_os.voice_interface import VoiceInterface

    v = VoiceInterface.__new__(VoiceInterface)
    v.config = {"tts_engine": "rumik"}
    assert VoiceInterface._privacy_tts_only_local(v) is True
    assert VoiceInterface._speak_rumik(v, "hi") is False
    assert VoiceInterface._speak_neural(v, "hi") is False


def test_rumik_toggle_off_skips_rumik(clean, tmp_path, monkeypatch):
    monkeypatch.setenv("PRIVACY__ALLOW_RUMIK_TTS", "false")
    reset_settings_cache()
    from access_os.voice_interface import VoiceInterface

    v = VoiceInterface.__new__(VoiceInterface)
    v.config = {"tts_engine": "rumik"}
    assert VoiceInterface._privacy_tts_only_local(v) is True
    assert VoiceInterface._speak_rumik(v, "hi") is False
