"""Single typed configuration for JARVIS (Master Plan Task 0.3).

Source of truth: :class:`Settings` (pydantic-settings).
- Non-secret values: ``settings.toml`` next to the app, or ``__``-nested
  env vars (e.g. ``VOICE__WAKE_WORD=friday``).
- Secrets: ``.env`` / environment variables ONLY. They are never written to
  ``settings.toml`` and never printed by :meth:`Settings.show`.

Legacy ``voice_config.json`` files are migrated ONE TIME into ``settings.toml``
by :func:`migrate_legacy_voice_config`; afterwards they are ignored.
``config.json`` (the old ACCESS-OS file) is deleted.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

logger = logging.getLogger(__name__)

APP_NAME = "JARVIS"
SETTINGS_FILE = "settings.toml"
ENV_FILE = ".env"


class VoiceCfg(BaseModel):
    language: str = "en-IN"
    wake_word: str = "jarvis"
    # F-07 fix: wake word REQUIRED by default. The mic must not act on
    # ambient audio without it.
    require_wake_word: bool = True
    # Task 1.6.2: push-to-talk (hold-to-talk). Off by default; when on, the
    # mic only captures while the hotkey is held. The hotkey itself is bound
    # by the platform layer (Windows) via ptt_press()/ptt_release().
    push_to_talk: bool = False
    push_to_talk_hotkey: str = "ctrl+alt+j"
    # Task 1.6.3: Privacy Mode — mic off entirely. No capture, no wake-word
    # scanning. Persisted; toggled from the GUI or `jarvis` CLI.
    privacy_mode: bool = False
    # F-18 fix: was a hardcoded 6.0s phrase_time_limit cutting long commands.
    max_utterance_s: float = 30.0
    tts_chain: List[str] = Field(default_factory=lambda: ["neural", "rumik", "pyttsx3"])
    tts_engine: str = "neural"
    rumik_model: str = "muga"
    neural_voice: str = "en-IN-NeerjaNeural"
    neural_voice_hi: str = "hi-IN-SwaraNeural"
    voice_rate: int = 160
    voice_volume: float = 1.0
    energy_threshold: int = 300  # legacy; VAD now uses a dynamic floor (3.3)
    pause_threshold: float = 0.8  # legacy; VAD hangover replaces this (3.3)
    # --- Phase 3: Voice 2.0 ---
    # 3.1 audio capture
    sample_rate: int = 16000
    frame_ms: int = 20
    preroll_s: float = 1.5
    input_device: Optional[int] = None  # None = system default
    aec_mode: str = "ducking"  # headset | ducking | webrtc
    noise_suppression: bool = False
    # 3.2 wake word
    wakeword_backend: str = "openwakeword"  # openwakeword | porcupine | dummy
    wakeword_threshold: float = 0.5
    followup_s: float = 7.0
    # 3.3 VAD
    vad_backend: str = "energy"  # energy | webrtc | silero
    vad_hangover_ms: int = 500
    # 3.4/3.5 STT
    stt_engine: str = "google"  # google | faster-whisper[:model] | sarvam | deepgram | scribe
    stt_language: str = "hi-en"
    # 3.6 streaming TTS
    tts_streaming: bool = True
    # 3.6 extra: XTTS v2 local neural voice (optional extra, see docs/XTTS_SETUP.md)
    xtts_speaker_wav: str = ""
    xtts_language: str = "en"
    xtts_device: str = "auto"
    # 7.4 voice identity: custom-voice consent gate. True means "this sample
    # is my own voice or I have the speaker's explicit consent". The gate in
    # voice/identity.py refuses any custom speaker_wav without this.
    voice_custom_consent: bool = False
    # 3.7 barge-in
    barge_in_enabled: bool = True
    barge_in_min_ms: int = 300
    barge_in_stop_ms: int = 250
    # 3.9 input modes: wakeword | ptt | typed | quiet
    input_mode: str = "wakeword"
    quiet_hours_start: str = ""  # "23:00" -> mic auto-off; empty = disabled
    quiet_hours_end: str = ""


class BrainCfg(BaseModel):
    ai_provider: str = "huggingface"
    provider_chain: List[str] = Field(
        default_factory=lambda: ["huggingface", "deepseek", "local"])
    hf_model: str = "Qwen/Qwen2.5-72B-Instruct"
    deepseek_model: str = "deepseek-chat"
    temperature: float = 0.3
    enable_ai_agent: bool = True
    fallback_to_local: bool = True
    # --- Phase 4: Brain 2.0 ---
    # 4.2 model router tiers (F-24: bake-off winners go here, never hard-coded)
    t1_model: str = ""  # fast: intent -> single tool, short Q&A
    t2_model: str = ""  # strong: planning, multi-step, coding
    t3_model: str = ""  # local: offline / privacy-mode (Ollama)
    daily_token_budget: int = 0  # 0 = unlimited
    daily_cost_inr_budget: float = 0.0  # 0 = unlimited
    semantic_cache_ttl_s: float = 600.0
    # 4.4 memory
    memory_db: str = ""  # empty = ~/.jarvis/memory.db
    memory_workspace: str = ""  # empty = ~/.jarvis/workspace (USER.md/MEMORY.md)
    # 4.6 skills
    skills_dir: str = "skills"
    # 4.1 agent loop hard limits
    loop_wall_time_s: float = 90.0


class SafetyCfg(BaseModel):
    # Phase 1 autonomy dial: 0=ask everything, 1=READ auto (default),
    # 2=READ+REVERSIBLE auto, 3=DESTRUCTIVE auto (SYSTEM always confirms).
    autonomy_level: int = 1
    confirm_timeout_s: float = 10.0
    max_tool_calls_per_minute: int = 20
    max_steps_per_task: int = 12
    # Task 8.3: safe mode — only reflex + READ tools run; everything above
    # READ is denied outright (fail-closed). Set via `jarvis --safe` or
    # settings.toml [safety] safe_mode = true.
    safe_mode: bool = False

    @field_validator("autonomy_level")
    @classmethod
    def _level_range(cls, v: int) -> int:
        if not 0 <= v <= 3:
            raise ValueError("autonomy_level must be 0..3")
        return v


class PrivacyCfg(BaseModel):
    # Privacy Mode = local-only chain: no mic/cloud STT, no cloud LLM/TTS.
    privacy_mode: bool = False
    # Task 8.3: offline mode — no network at all. Forces every cloud egress
    # flag off (via cloud_egress_allowed), swaps PIM providers to fakes, and
    # makes the policy gate deny tools with the "network" scope.
    offline: bool = False
    # Task 8.3: crash-report upload is OPT-IN only (default: local reports,
    # nothing leaves the machine). Both must be set for an upload to happen.
    crash_upload: bool = False
    crash_upload_url: str = ""
    # Task 1.10: per-provider egress toggles. Privacy Mode forces every
    # cloud call off regardless of these.
    allow_huggingface: bool = True   # chat text -> HF router (Qwen)
    allow_deepseek: bool = True      # chat text -> DeepSeek
    allow_rumik_tts: bool = True     # TTS text -> Rumik API
    allow_google_stt: bool = True    # mic audio -> Google Speech Recognition


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file=SETTINGS_FILE,
        env_file=ENV_FILE,
        env_nested_delimiter="__",
        extra="ignore",
    )

    app_name: str = APP_NAME
    voice: VoiceCfg = VoiceCfg()
    brain: BrainCfg = BrainCfg()
    safety: SafetyCfg = SafetyCfg()
    privacy: PrivacyCfg = PrivacyCfg()

    # --- Secrets: env/.env only, never settings.toml, never logged ---
    huggingface_api_key: str = ""
    deepseek_api_key: str = ""
    rumik_api_key: str = ""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Priority: explicit init kwargs > env vars > .env file >
        # settings.toml > docker-style file secrets.
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    def masked_dict(self) -> Dict[str, Any]:
        """Effective config with every secret masked. Safe to print/log."""
        d = self.model_dump()
        for key in ("huggingface_api_key", "deepseek_api_key", "rumik_api_key"):
            d[key] = "***set***" if d.get(key) else ""
        return d

    def show(self) -> str:
        """Human-readable masked config for `jarvis config show`."""
        lines = [f"# {self.app_name} effective configuration (secrets masked)"]
        d = self.masked_dict()
        for section in ("voice", "brain", "safety", "privacy"):
            lines.append(f"\n[{section}]")
            for k, v in d[section].items():
                lines.append(f"{k} = {v!r}")
        lines.append("\n[secrets]")
        for k in ("huggingface_api_key", "deepseek_api_key", "rumik_api_key"):
            lines.append(f"{k} = {d[k]!r}")
        return "\n".join(lines)

    def legacy_voice_dict(self) -> Dict[str, Any]:
        """Flat dict matching the old voice_config.json keys.

        Lets the existing VoiceInterface keep working unchanged while the
        single source of truth is this Settings object.
        """
        v, b = self.voice, self.brain
        return {
            "language": v.language,
            "wake_word": v.wake_word,
            "require_wake_word": v.require_wake_word,
            "push_to_talk": v.push_to_talk,
            "push_to_talk_hotkey": v.push_to_talk_hotkey,
            "privacy_mode": v.privacy_mode,
            "max_utterance_s": v.max_utterance_s,
            "phrase_time_limit": v.max_utterance_s,  # legacy alias
            "energy_threshold": v.energy_threshold,
            "pause_threshold": v.pause_threshold,
            "voice_rate": v.voice_rate,
            "voice_volume": v.voice_volume,
            "tts_engine": v.tts_engine,
            "rumik_model": v.rumik_model,
            "neural_voice": v.neural_voice,
            "assistant_name": self.app_name,
            "enable_ai_agent": b.enable_ai_agent,
            "ai_provider": b.ai_provider,
            "hf_model": b.hf_model,
            "deepseek_model": b.deepseek_model,
            "ai_temperature": b.temperature,
            "fallback_to_local": b.fallback_to_local,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached single Settings instance for the process."""
    s = Settings()
    # Task 1.9: backfill empty secret fields from the OS keyring
    # (best-effort; env/.env already handled by pydantic-settings).
    try:
        from jarvis.core.secrets import get_secret
        if not s.huggingface_api_key:
            s.huggingface_api_key = get_secret("HUGGINGFACE_API_KEY")
        if not s.deepseek_api_key:
            s.deepseek_api_key = get_secret("DEEPSEEK_API_KEY")
        if not s.rumik_api_key:
            s.rumik_api_key = get_secret("RUMIK_API_KEY")
    except Exception:
        pass
    return s


def reset_settings_cache() -> None:
    """Drop the cached Settings (mainly for tests)."""
    get_settings.cache_clear()


def cloud_egress_allowed(settings: "Settings") -> bool:
    """True if any cloud network call (STT/TTS/LLM) may happen.

    Task 8.3: offline mode forces this False regardless of the individual
    allow_* toggles. Callers check this *in addition to* their specific
    allow_* flag, so one switch kills all cloud egress.
    """
    return not (settings.privacy.offline or settings.privacy.privacy_mode)


# ---------------------------------------------------------------------------
# Legacy migration (voice_config.json -> settings.toml, one time)
# ---------------------------------------------------------------------------

_LEGACY_MAP = {
    # legacy key -> (section, settings key)
    "language": ("voice", "language"),
    "wake_word": ("voice", "wake_word"),
    "require_wake_word": ("voice", "require_wake_word"),
    "push_to_talk": ("voice", "push_to_talk"),
    "push_to_talk_hotkey": ("voice", "push_to_talk_hotkey"),
    "privacy_mode": ("voice", "privacy_mode"),
    "phrase_time_limit": ("voice", "max_utterance_s"),
    "energy_threshold": ("voice", "energy_threshold"),
    "pause_threshold": ("voice", "pause_threshold"),
    "voice_rate": ("voice", "voice_rate"),
    "voice_volume": ("voice", "voice_volume"),
    "tts_engine": ("voice", "tts_engine"),
    "rumik_model": ("voice", "rumik_model"),
    "neural_voice": ("voice", "neural_voice"),
    "ai_provider": ("brain", "ai_provider"),
    "hf_model": ("brain", "hf_model"),
    "deepseek_model": ("brain", "deepseek_model"),
    "ai_temperature": ("brain", "temperature"),
    "enable_ai_agent": ("brain", "enable_ai_agent"),
    "fallback_to_local": ("brain", "fallback_to_local"),
}


def _toml_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    return json.dumps(str(v))  # quoted string


def _write_settings_toml(settings: Settings, path: str = SETTINGS_FILE) -> None:
    """Write non-secret settings as TOML. Secrets are NEVER written here."""
    lines = [
        "# JARVIS settings — generated/migrated automatically.",
        "# Secrets live in .env, never in this file.",
        "",
    ]
    for section in ("voice", "brain", "safety", "privacy"):
        lines.append(f"[{section}]")
        for k, v in settings.model_dump()[section].items():
            if v is None:
                continue  # unset optionals stay at their default on read
            lines.append(f"{k} = {_toml_value(v)}")
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def migrate_legacy_voice_config(legacy_path: str = "voice_config.json",
                                dest: str = SETTINGS_FILE) -> bool:
    """One-time migration: legacy voice_config.json -> settings.toml.

    Runs only when ``dest`` does not exist yet and the legacy file does.
    Returns True when a migration was performed.
    """
    if os.path.exists(dest) or not os.path.exists(legacy_path):
        return False
    try:
        legacy = json.loads(Path(legacy_path).read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Could not read legacy {legacy_path}: {e}")
        return False
    data: Dict[str, Dict[str, Any]] = {}
    for legacy_key, (section, new_key) in _LEGACY_MAP.items():
        if legacy_key in legacy:
            data.setdefault(section, {})[new_key] = legacy[legacy_key]
    try:
        settings = Settings(**data)
    except Exception as e:
        logger.error(f"Legacy config failed validation, using defaults: {e}")
        settings = Settings()
    _write_settings_toml(settings, dest)
    reset_settings_cache()
    logger.info(f"Migrated legacy {legacy_path} -> {dest}; "
                f"{legacy_path} is now ignored.")
    return True


def save_legacy_voice_dict(d: Dict[str, Any], dest: str = SETTINGS_FILE) -> None:
    """Persist a flat legacy-style voice dict back through Settings."""
    data: Dict[str, Dict[str, Any]] = {}
    for legacy_key, (section, new_key) in _LEGACY_MAP.items():
        if legacy_key in d:
            data.setdefault(section, {})[new_key] = d[legacy_key]
    # Keep any non-legacy sections from the current settings.
    current = get_settings()
    merged = current.model_dump()
    for section, values in data.items():
        merged[section].update(values)
    merged.pop("huggingface_api_key", None)
    merged.pop("deepseek_api_key", None)
    merged.pop("rumik_api_key", None)
    settings = Settings(**merged)
    _write_settings_toml(settings, dest)
    reset_settings_cache()


def main(argv: Optional[list] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["show"]:
        migrate_legacy_voice_config()
        print(get_settings().show())
        return 0
    print("usage: python -m access_os.config show")
    return 2


if __name__ == "__main__":
    sys.exit(main())
