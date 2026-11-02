"""Voice identity (Master Plan Task 7.4).

Two jobs:

1. **Consistency across tiers.** The TTS chain (neural -> rumik -> pyttsx3 ->
   xtts) swaps engines on failure; without normalization the assistant sounds
   like a different person each time. ``VoiceIdentity`` holds per-engine
   volume/pitch/rate trims so every tier lands near the same perceived voice.

2. **Custom-voice consent gate.** XTTS can clone any 6-second sample. That power
   is gated: a custom ``speaker_wav`` is used ONLY when the user has explicitly
   opted in (``voice_custom_consent=true`` in settings, meaning "this is my own
   voice or I have the speaker's explicit consent"). Cloning someone else's
   voice is refused by design — the check lives here, not in the UI, so no
   caller can bypass it by accident.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class EngineTrim:
    """Per-engine normalization trims. Ranges are conservative on purpose."""
    volume: float = 1.0   # 0.0 .. 1.5 multiplier
    rate: int = 0         # -10 .. +10 (Edge-TTS style offset)
    pitch: int = 0        # -10 .. +10 semitone-ish offset, where supported


# Measured-ish defaults so tiers sound close. Tuned further on real hardware
# (docs/VOICE_IDENTITY_TEST.md in Phase 8).
DEFAULT_TRIMS: Dict[str, EngineTrim] = {
    "neural": EngineTrim(volume=1.0, rate=0, pitch=0),
    "rumik": EngineTrim(volume=0.95, rate=0, pitch=0),
    "pyttsx3": EngineTrim(volume=1.0, rate=0, pitch=0),
    "xtts": EngineTrim(volume=1.0, rate=0, pitch=0),
}


@dataclass
class VoiceIdentity:
    """The assistant's single voice identity across all TTS tiers."""
    voice_name: str = "en-IN-NeerjaNeural"
    voice_name_hi: str = "hi-IN-SwaraNeural"
    trims: Dict[str, EngineTrim] = field(
        default_factory=lambda: {k: EngineTrim(v.volume, v.rate, v.pitch)
                                 for k, v in DEFAULT_TRIMS.items()})

    def trim_for(self, engine: str) -> EngineTrim:
        return self.trims.get(engine, EngineTrim())

    def describe(self) -> Dict[str, object]:
        return {
            "voice": self.voice_name,
            "voice_hi": self.voice_name_hi,
            "trims": {k: {"volume": t.volume, "rate": t.rate, "pitch": t.pitch}
                      for k, t in self.trims.items()},
        }


def resolve_speaker_wav(configured_wav: str, consent: bool) -> Optional[str]:
    """Consent gate for custom XTTS voices (7.4).

    Returns the wav path only when ALL hold:
      - user explicitly opted in (``voice_custom_consent=true``),
      - the path exists and is a file,
      - the path is inside the JARVIS workspace or data dir (no
        ``C:\\Users\\SomeoneElse\\...`` surprises).

    Otherwise returns None and logs why — the caller must fall back to the
    default voice, never to an unconsented sample.
    """
    if not configured_wav:
        return None
    if not consent:
        logger.warning("custom speaker_wav configured but voice_custom_consent "
                       "is not set — refusing (7.4 consent gate)")
        return None
    p = Path(configured_wav).expanduser()
    if not p.is_file():
        logger.warning("custom speaker_wav not found: %s", configured_wav)
        return None
    # Keep the sample inside JARVIS-owned dirs.
    jarvis_roots = [Path.home() / ".jarvis", Path.home() / "jarvis-workspace"]
    try:
        resolved = p.resolve()
    except OSError:
        return None
    if not any(str(resolved).startswith(str(r)) for r in jarvis_roots):
        logger.warning("custom speaker_wav outside JARVIS dirs — refusing: %s",
                       resolved)
        return None
    return str(resolved)
