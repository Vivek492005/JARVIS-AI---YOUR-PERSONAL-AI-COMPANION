"""Speech-to-text providers (Master Plan Tasks 3.4, 3.5).

Every engine implements :py:class:`STTEngine`:

- ``transcribe(audio, language)`` — batch: one WAV worth of 16-bit mono
  PCM → :py:class:`Transcription`.
- ``stream(frames, language)`` — streaming: yields partial
  transcriptions (``is_final=False``) then a final. The default
  implementation buffers everything and yields a single final, so batch
  engines work in streaming pipelines (with higher latency).

Engines (all heavy deps lazy):
- ``google`` — SpeechRecognition + Google Web Speech (current default).
  Free, no key, cloud. Not streaming, not offline.
- ``faster-whisper`` — local, offline. The plan warns stock large-v3 is
  weak on Hinglish (~30 WER reported); community Hinglish-tuned
  checkpoints can be pointed at via ``model_path``.
- ``sarvam`` — Sarvam AI Saaras, Indic specialist, streaming-capable.
- ``deepgram`` — Deepgram Nova-3, strong on code-switching per
  third-party reports.
- ``scribe`` — ElevenLabs Scribe, lowest overall WER in one Indian-
  language report.

Task 3.4 (bake-off): run ``evals/stt/stt_bakeoff.py`` on real hardware
with real utterances; see ``docs/DECISION_STT.md`` for the provisional
pick and how to re-run the decision with data.
"""

from __future__ import annotations

import io
import logging
import time
import wave
from dataclasses import dataclass
from typing import Dict, Iterator, List, Protocol

logger = logging.getLogger(__name__)


@dataclass
class Transcription:
    text: str
    confidence: float = 0.0
    latency_s: float = 0.0
    language: str = "hi-en"
    is_final: bool = True
    engine: str = ""


class STTEngine(Protocol):
    """One STT backend behind a uniform interface."""

    @property
    def name(self) -> str: ...

    @property
    def offline_capable(self) -> bool: ...

    @property
    def supports_streaming(self) -> bool: ...

    def transcribe(
        self, audio: bytes, language: str = "hi-en", sample_rate: int = 16000
    ) -> Transcription:
        """Batch transcription of one utterance."""
        ...

    def stream(
        self, frames: Iterator[bytes], language: str = "hi-en", sample_rate: int = 16000
    ) -> Iterator[Transcription]:
        """Yield partials (is_final=False), then exactly one final."""
        ...


class _BaseEngine:
    """Default batch-fallback streaming: buffer, then one final."""

    @property
    def supports_streaming(self) -> bool:
        return False

    def stream(
        self, frames: Iterator[bytes], language: str = "hi-en", sample_rate: int = 16000
    ) -> Iterator[Transcription]:
        audio = b"".join(frames)
        if audio:
            yield self.transcribe(audio, language, sample_rate)


def _pcm_to_wav(audio: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(audio)
    return buf.getvalue()


class GoogleSTTEngine(_BaseEngine):
    """Current default: SpeechRecognition + Google Web Speech (free, cloud)."""

    name = "google"
    offline_capable = False

    def transcribe(
        self, audio: bytes, language: str = "hi-en", sample_rate: int = 16000
    ) -> Transcription:
        import speech_recognition as sr

        t0 = time.monotonic()
        rec = sr.Recognizer()
        wav = _pcm_to_wav(audio, sample_rate)
        with sr.AudioFile(io.BytesIO(wav)) as source:
            data = rec.record(source)
        # "hi-IN" covers Hinglish reasonably; cloud call.
        try:
            text = rec.recognize_google(data, language="hi-IN")
        except sr.UnknownValueError:
            text = ""
        except Exception as e:
            logger.warning(f"Google STT failed: {e}")
            text = ""
        return Transcription(
            text=text,
            confidence=0.8 if text else 0.0,
            latency_s=time.monotonic() - t0,
            language=language,
            engine=self.name,
        )


class FasterWhisperEngine(_BaseEngine):
    """Local faster-whisper. ``model`` may be a size or a local path
    (e.g. a Hinglish-tuned checkpoint)."""

    def __init__(
        self, model: str = "large-v3", device: str = "auto", compute_type: str = "int8"
    ) -> None:
        self._model_name = model
        self._device = device
        self._compute_type = compute_type
        self._model = None

    @property
    def name(self) -> str:
        return f"faster-whisper:{self._model_name}"

    @property
    def offline_capable(self) -> bool:
        return True

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise RuntimeError(
                    "faster-whisper is not installed. Install with "
                    "`pip install jarvis-assistant[stt-local]` (see docs/AUDIO_SETUP.md)."
                ) from e
            device = self._device
            if device == "auto":
                device = "cuda" if _cuda_available() else "cpu"
            self._model = WhisperModel(
                self._model_name, device=device, compute_type=self._compute_type
            )
        return self._model

    def transcribe(
        self, audio: bytes, language: str = "hi-en", sample_rate: int = 16000
    ) -> Transcription:
        import numpy as np

        t0 = time.monotonic()
        model = self._load()
        pcm = np.frombuffer(audio, dtype=np.int16).astype("float32") / 32768.0
        # faster-whisper takes file paths or arrays; feed float array.
        segments, info = model.transcribe(
            pcm, language="hi" if language.startswith("hi") else "en", vad_filter=True
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        conf = float(info.language_probability) if info else 0.0
        return Transcription(
            text=text,
            confidence=conf,
            latency_s=time.monotonic() - t0,
            language=language,
            engine=self.name,
        )


def _cuda_available() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False


class _HttpEngine(_BaseEngine):
    """Shared bits for cloud HTTP STT APIs (key via secrets, never code)."""

    def _post(
        self, url: str, headers: Dict[str, str], files=None, data=None, timeout: float = 30.0
    ) -> dict:
        try:
            import httpx
        except ImportError as e:
            raise RuntimeError("httpx is not installed") from e
        resp = httpx.post(url, headers=headers, files=files, data=data, timeout=timeout)
        resp.raise_for_status()
        return resp.json()


class SarvamEngine(_HttpEngine):
    """Sarvam AI Saaras — Indic specialist, streaming-capable API."""

    name = "sarvam"
    offline_capable = False
    supports_streaming = True  # API supports it; this adapter does batch

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    def _key(self) -> str:
        if self._api_key:
            return self._api_key
        from jarvis.core.secrets import get_secret

        key = get_secret("SARVAM_API_KEY")
        if not key:
            raise RuntimeError("SARVAM_API_KEY not set (secrets/env).")
        return key

    def transcribe(
        self, audio: bytes, language: str = "hi-en", sample_rate: int = 16000
    ) -> Transcription:
        t0 = time.monotonic()
        data = self._post(
            "https://api.sarvam.ai/speech-to-text",
            headers={"api-subscription-key": self._key()},
            files={"file": ("audio.wav", _pcm_to_wav(audio, sample_rate), "audio/wav")},
            data={"language_code": "hi-IN", "model": "saaras:v2"},
        )
        text = data.get("transcript", "")
        return Transcription(
            text=text,
            confidence=0.85 if text else 0.0,
            latency_s=time.monotonic() - t0,
            language=language,
            engine=self.name,
        )


class DeepgramEngine(_HttpEngine):
    """Deepgram Nova-3 — strong code-switching per third-party reports."""

    name = "deepgram"
    offline_capable = False

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    def _key(self) -> str:
        if self._api_key:
            return self._api_key
        from jarvis.core.secrets import get_secret

        key = get_secret("DEEPGRAM_API_KEY")
        if not key:
            raise RuntimeError("DEEPGRAM_API_KEY not set (secrets/env).")
        return key

    def transcribe(
        self, audio: bytes, language: str = "hi-en", sample_rate: int = 16000
    ) -> Transcription:
        t0 = time.monotonic()
        try:
            import httpx
        except ImportError as e:
            raise RuntimeError("httpx is not installed") from e
        resp = httpx.post(
            "https://api.deepgram.com/v1/listen?model=nova-3&language=multi",
            headers={"Authorization": f"Token {self._key()}", "Content-Type": "audio/wav"},
            content=_pcm_to_wav(audio, sample_rate),
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        try:
            alt = data["results"]["channels"][0]["alternatives"][0]
            text, conf = alt.get("transcript", ""), float(alt.get("confidence", 0.0))
        except (KeyError, IndexError):
            text, conf = "", 0.0
        return Transcription(
            text=text,
            confidence=conf,
            latency_s=time.monotonic() - t0,
            language=language,
            engine=self.name,
        )


class ScribeEngine(_HttpEngine):
    """ElevenLabs Scribe — lowest WER in one Indian-language report."""

    name = "scribe"
    offline_capable = False

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    def _key(self) -> str:
        if self._api_key:
            return self._api_key
        from jarvis.core.secrets import get_secret

        key = get_secret("ELEVENLABS_API_KEY")
        if not key:
            raise RuntimeError("ELEVENLABS_API_KEY not set (secrets/env).")
        return key

    def transcribe(
        self, audio: bytes, language: str = "hi-en", sample_rate: int = 16000
    ) -> Transcription:
        t0 = time.monotonic()
        data = self._post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": self._key()},
            files={"file": ("audio.wav", _pcm_to_wav(audio, sample_rate), "audio/wav")},
            data={"model_id": "scribe_v1"},
        )
        text = data.get("text", "")
        return Transcription(
            text=text,
            confidence=0.85 if text else 0.0,
            latency_s=time.monotonic() - t0,
            language=language,
            engine=self.name,
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_ENGINES: Dict[str, type] = {
    "google": GoogleSTTEngine,
    "faster-whisper": FasterWhisperEngine,
    "sarvam": SarvamEngine,
    "deepgram": DeepgramEngine,
    "scribe": ScribeEngine,
}


def list_engines() -> List[str]:
    return sorted(_ENGINES)


def make_engine(name: str, **kwargs) -> STTEngine:
    """Instantiate an engine by name (``faster-whisper:medium`` form OK)."""
    base, _, arg = name.partition(":")
    if base not in _ENGINES:
        raise ValueError(f"unknown STT engine {name!r}; choose from {list_engines()}")
    if base == "faster-whisper" and arg:
        kwargs.setdefault("model", arg)
    return _ENGINES[base](**kwargs)
