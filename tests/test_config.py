"""Tests for Task 0.3: the single typed Settings object (access_os/config.py)."""

import json

import pytest
from pydantic import ValidationError

from access_os.config import (
    Settings,
    get_settings,
    migrate_legacy_voice_config,
    reset_settings_cache,
    save_legacy_voice_dict,
)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Run each test in an empty dir with a fresh Settings cache."""
    monkeypatch.chdir(tmp_path)
    reset_settings_cache()
    yield tmp_path
    reset_settings_cache()


def test_safe_defaults(isolated):
    s = get_settings()
    # F-07: wake word REQUIRED by default
    assert s.voice.require_wake_word is True
    # F-18: long-utterance default (was hardcoded 6.0s)
    assert s.voice.max_utterance_s == 30.0
    assert s.voice.wake_word == "jarvis"
    assert s.safety.autonomy_level == 1
    assert s.safety.confirm_timeout_s == 10.0
    assert s.privacy.privacy_mode is False
    # secrets default to empty, never hardcoded
    assert s.huggingface_api_key == ""
    assert s.deepseek_api_key == ""
    assert s.rumik_api_key == ""


def test_invalid_values_rejected(isolated):
    with pytest.raises(ValidationError):
        Settings(safety={"autonomy_level": 5})
    with pytest.raises(ValidationError):
        Settings(voice={"require_wake_word": "maybe"})


def test_env_override(isolated, monkeypatch):
    monkeypatch.setenv("VOICE__WAKE_WORD", "friday")
    monkeypatch.setenv("SAFETY__AUTONOMY_LEVEL", "2")
    s = get_settings()
    assert s.voice.wake_word == "friday"
    assert s.safety.autonomy_level == 2


def test_secrets_from_env_only(isolated, monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "hf_test_123")
    s = get_settings()
    assert s.huggingface_api_key == "hf_test_123"


def test_legacy_migration(isolated):
    legacy = {
        "wake_word": "JARVIS",
        "require_wake_word": False,   # explicit user choice is preserved
        "phrase_time_limit": 6.0,     # mapped -> max_utterance_s
        "voice_rate": 175,
        "ai_temperature": 0.5,
    }
    (isolated / "voice_config.json").write_text(json.dumps(legacy))
    assert migrate_legacy_voice_config("voice_config.json") is True
    assert (isolated / "settings.toml").exists()
    # legacy file left untouched
    assert json.loads((isolated / "voice_config.json").read_text()) == legacy
    s = get_settings()
    assert s.voice.require_wake_word is False
    assert s.voice.max_utterance_s == 6.0
    assert s.voice.voice_rate == 175
    assert s.brain.temperature == 0.5
    # second run is a no-op
    assert migrate_legacy_voice_config("voice_config.json") is False


def test_no_migration_without_legacy_file(isolated):
    assert migrate_legacy_voice_config("voice_config.json") is False
    assert not (isolated / "settings.toml").exists()


def test_show_masks_secrets(isolated, monkeypatch, capsys):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "hf_super_secret_value")
    from access_os.config import main
    assert main(["show"]) == 0
    out = capsys.readouterr().out
    assert "hf_super_secret_value" not in out
    assert "***set***" in out
    assert "require_wake_word" in out


def test_legacy_voice_dict_shape(isolated):
    d = get_settings().legacy_voice_dict()
    for key in ("wake_word", "require_wake_word", "max_utterance_s",
                "phrase_time_limit", "energy_threshold", "tts_engine",
                "hf_model", "ai_temperature", "enable_ai_agent"):
        assert key in d, key


def test_save_legacy_voice_dict_roundtrip(isolated):
    s = get_settings()
    d = s.legacy_voice_dict()
    d["voice_rate"] = 200
    save_legacy_voice_dict(d)
    s2 = get_settings()
    assert s2.voice.voice_rate == 200
    # secrets never land in the toml
    toml = (isolated / "settings.toml").read_text()
    assert "api_key" not in toml.lower()
