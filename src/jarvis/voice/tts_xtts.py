"""XTTS v2 local neural TTS engine (Task 3.6 extra, user-approved).

Coqui XTTS v2: fully offline, no API key, no quota — and voice-cloning
capable (give it a ~6 s WAV of any voice, it speaks as that voice).
This is the "never exhausts" answer to key-based TTS, and the most
human-like free option available.

Setup (see docs/XTTS_SETUP.md):
    pip install jarvis-assistant[xtts]     # pulls coqui-tts (~2 GB model on first run)
    # put a 6-second 16 kHz WAV at the configured speaker_wav path
    # settings.toml: tts_engine = "xtts"

The import is lazy: importing this module never imports ``TTS``. The
model loads on first synth (slow, ~10-30 s) and is then reused.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"


class XTTSEngine:
    """Coqui XTTS v2 provider. Offline, voice-cloning, no key."""

    def __init__(self, model_name: str = DEFAULT_MODEL,
                 speaker_wav: str = "",
                 language: str = "en",
                 device: str = "auto") -> None:
        self.model_name = model_name
        self.speaker_wav = speaker_wav
        self.language = language
        self._device = device
        self._tts = None

    @property
    def name(self) -> str:
        return "xtts"

    @property
    def offline_capable(self) -> bool:
        return True

    def _load(self):
        if self._tts is None:
            try:
                from TTS.api import TTS
            except ImportError as e:
                raise RuntimeError(
                    "coqui-tts is not installed. Install with "
                    "`pip install jarvis-assistant[xtts]` and see "
                    "docs/XTTS_SETUP.md."
                ) from e
            device = self._device
            if device == "auto":
                device = "cuda" if self._cuda() else "cpu"
                logger.info(f"XTTS using device: {device}")
            # First run downloads ~2 GB.
            self._tts = TTS(self.model_name).to(device)
        return self._tts

    @staticmethod
    def _cuda() -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def synth(self, text: str, voice: Optional[str] = None) -> bytes:
        """Synthesize; returns WAV bytes. ``voice`` overrides speaker_wav."""
        tts = self._load()
        speaker = voice or self.speaker_wav
        if not speaker or not os.path.exists(speaker):
            raise RuntimeError(
                "XTTS needs a speaker reference WAV (~6 s, 16 kHz mono). "
                f"Configured path {speaker!r} does not exist. "
                "See docs/XTTS_SETUP.md."
            )
        t0 = time.monotonic()
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="jarvis-xtts-")
        os.close(fd)
        try:
            tts.tts_to_file(text=text, speaker_wav=speaker,
                            language=self.language, file_path=path)
            with open(path, "rb") as f:
                data = f.read()
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        logger.debug(f"xtts synth {len(text)} chars in {time.monotonic()-t0:.1f}s")
        return data

    def synth_stream(self, sentences, voice: Optional[str] = None):
        from jarvis.voice.tts import AudioChunk
        for i, s in enumerate(sentences):
            data = self.synth(s, voice)
            if data:
                yield AudioChunk(data=data, index=i, text=s, engine=self.name)


def check_xtts() -> tuple:
    """(ok, detail) for ``jarvis doctor``."""
    try:
        import TTS  # noqa: F401
        return True, "coqui-tts installed"
    except ImportError:
        return False, "coqui-tts not installed (pip install jarvis-assistant[xtts])"
