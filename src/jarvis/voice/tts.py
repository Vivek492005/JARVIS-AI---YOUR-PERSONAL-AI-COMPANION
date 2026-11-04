"""Streaming TTS (Master Plan Task 3.6).

Pipeline: LLM token stream -> :py:class:`SentenceSplitter` -> synth queue
-> player. The first sentence starts playing as soon as it's ready; the
plan's target is first-token -> first-audio <= 300 ms for short replies.

Pieces:
- :py:class:`TTSProvider` — ``synth(text, voice) -> bytes`` (MP3/WAV),
  optional ``synth_stream``.
- :py:class:`SentenceSplitter` — splits on ``.``, ``?``, ``!``, ``।``,
  newlines.
- :py:func:`detect_script` — per-sentence Hindi (Devanagari) vs English
  (Latin) detection for voice switching. Hinglish in Latin script stays
  on the multilingual voice.
- :py:class:`StreamingTTS` — consumes a token iterator, synthesizes
  sentence by sentence on a worker thread, calls ``on_audio(chunk, idx)``.
- :py:func:`speak_style` — spoken-reply rules: <= 2 sentences, no URLs /
  code read aloud, numbers spelled sanely.
- :py:class:`PhraseCache` — pre-synthesized repeated phrases
  ("Done", "Samajh gaya").

Engines live here as providers: :py:class:`EdgeTTSEngine`,
:py:class:`RumikTTSEngine`, :py:class:`Pyttsx3Engine`. The XTTS v2 local
neural engine is :py:mod:`jarvis.voice.tts_xtts` (optional extra).
"""

from __future__ import annotations

import hashlib
import logging
import os
import queue
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterator, List, Optional, Protocol

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentence splitting + script detection
# ---------------------------------------------------------------------------

_SENT_END = re.compile(r"(.+?[.!?।\n]+)(?=\s|$)", re.DOTALL)
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")


class SentenceSplitter:
    """Incremental sentence splitter for token streams."""

    def __init__(self) -> None:
        self._buf = ""

    def feed(self, token: str) -> List[str]:
        """Feed one token; returns newly completed sentences."""
        self._buf += token
        out: List[str] = []
        while True:
            m = _SENT_END.match(self._buf)
            if not m:
                break
            sent = m.group(1).strip()
            if sent:
                out.append(sent)
            self._buf = self._buf[m.end() :]
        return out

    def flush(self) -> List[str]:
        """Return any trailing partial sentence."""
        rest = self._buf.strip()
        self._buf = ""
        return [rest] if rest else []


def detect_script(sentence: str) -> str:
    """'hi' if the sentence is Devanagari-dominant, else 'en'.

    Latin-script Hinglish ("chrome khol de") returns 'en' — it goes to the
    multilingual voice, which handles code-switching better than switching
    voices mid-reply.
    """
    if not sentence.strip():
        return "en"
    dev = len(_DEVANAGARI.findall(sentence))
    latin = len(re.findall(r"[A-Za-z]", sentence))
    total = dev + latin
    if total == 0:
        return "en"
    return "hi" if dev / total > 0.4 else "en"


# ---------------------------------------------------------------------------
# Spoken-reply style rules (plan 3.6.5)
# ---------------------------------------------------------------------------

_URL = re.compile(r"https?://\S+|www\.\S+")
_CODE = re.compile(r"```.*?```", re.DOTALL)


def speak_style(text: str, max_sentences: int = 2) -> str:
    """Make LLM text speakable: strip URLs/code, cap sentence count."""
    text = _CODE.sub("code snippet", text)
    text = _URL.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    splitter = SentenceSplitter()
    sents: List[str] = []
    for tok in text.split(" "):
        sents.extend(splitter.feed(tok + " "))
    sents.extend(splitter.flush())
    sents = [s for s in sents if s]
    if len(sents) > max_sentences:
        sents = sents[:max_sentences]
    return " ".join(sents)


# ---------------------------------------------------------------------------
# Provider interface + engines
# ---------------------------------------------------------------------------


@dataclass
class AudioChunk:
    data: bytes  # encoded audio (mp3/wav), ready to play
    index: int  # sentence index
    text: str = ""  # source sentence (for the HUD)
    engine: str = ""


class TTSProvider(Protocol):
    """A TTS backend behind one interface."""

    @property
    def name(self) -> str: ...

    @property
    def offline_capable(self) -> bool: ...

    def synth(self, text: str, voice: Optional[str] = None) -> bytes:
        """Synthesize one sentence; returns encoded audio bytes."""
        ...

    def synth_stream(
        self, sentences: Iterator[str], voice: Optional[str] = None
    ) -> Iterator[AudioChunk]:
        """Default: synth each sentence sequentially."""
        ...


class _BaseTTS:
    @property
    def offline_capable(self) -> bool:
        return False

    def synth_stream(
        self, sentences: Iterator[str], voice: Optional[str] = None
    ) -> Iterator[AudioChunk]:
        for i, s in enumerate(sentences):
            data = self.synth(s, voice)
            if data:
                yield AudioChunk(data=data, index=i, text=s, engine=self.name)


def _save_edge_tts(text: str, voice: str) -> bytes:
    """Run edge-tts, return MP3 bytes. Raises on failure."""
    import asyncio
    import edge_tts

    async def _run() -> bytes:
        comm = edge_tts.Communicate(text, voice)
        fd, path = tempfile.mkstemp(suffix=".mp3", prefix="jarvis-tts-")
        os.close(fd)
        try:
            await comm.save(path)
            with open(path, "rb") as f:
                return f.read()
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(_run())
    finally:
        loop.close()


class EdgeTTSEngine(_BaseTTS):
    """Microsoft Edge neural voices. Free, no key, no quota."""

    def __init__(
        self, voice_en: str = "en-IN-NeerjaNeural", voice_hi: str = "hi-IN-SwaraNeural"
    ) -> None:
        self.voice_en = voice_en
        self.voice_hi = voice_hi

    @property
    def name(self) -> str:
        return "edge"

    def synth(self, text: str, voice: Optional[str] = None) -> bytes:
        try:
            import edge_tts  # noqa: F401
        except ImportError as e:
            raise RuntimeError("edge-tts is not installed (`pip install edge-tts`).") from e
        v = voice or (self.voice_hi if detect_script(text) == "hi" else self.voice_en)
        t0 = time.monotonic()
        data = _save_edge_tts(text, v)
        logger.debug(f"edge-tts synth {len(text)} chars in {time.monotonic() - t0:.2f}s")
        return data


class RumikTTSEngine(_BaseTTS):
    """Rumik AI Silk TTS (API key via secrets). Kept as fallback tier."""

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "rumik"

    def _key(self) -> str:
        if self._api_key:
            return self._api_key
        from jarvis.core.secrets import get_secret

        key = get_secret("RUMIK_API_KEY")
        if not key:
            raise RuntimeError("RUMIK_API_KEY not set (secrets/env).")
        return key

    def synth(self, text: str, voice: Optional[str] = None) -> bytes:
        try:
            import httpx
        except ImportError as e:
            raise RuntimeError("httpx is not installed") from e
        url = os.getenv("RUMIK_API_URL", "https://silk-api.rumik.ai/v1/tts")
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {self._key()}", "Content-Type": "application/json"},
            json={"text": text, "voice": voice or "default"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.content


class Pyttsx3Engine(_BaseTTS):
    """Offline pyttsx3 fallback. Robotic, but always available."""

    def __init__(self) -> None:
        self._engine = None

    @property
    def name(self) -> str:
        return "pyttsx3"

    @property
    def offline_capable(self) -> bool:
        return True

    def synth(self, text: str, voice: Optional[str] = None) -> bytes:
        # pyttsx3 speaks directly; no bytes to return. The streaming
        # pipeline treats empty bytes as "played inline".
        try:
            import pyttsx3
        except ImportError as e:
            raise RuntimeError("pyttsx3 is not installed") from e
        if self._engine is None:
            self._engine = pyttsx3.init()
        self._engine.say(text)
        self._engine.runAndWait()
        return b""


# ---------------------------------------------------------------------------
# Phrase cache
# ---------------------------------------------------------------------------


class PhraseCache:
    """Pre-synthesized audio for repeated phrases ("Done", ...)."""

    def __init__(self, provider: TTSProvider, max_items: int = 64) -> None:
        self.provider = provider
        self._cache: Dict[str, bytes] = {}
        self._max = max_items
        self._lock = threading.Lock()

    def _key(self, text: str, voice: Optional[str]) -> str:
        return hashlib.sha256(f"{voice or ''}|{text}".encode()).hexdigest()[:16]

    def get(self, text: str, voice: Optional[str] = None) -> bytes:
        k = self._key(text, voice)
        with self._lock:
            if k in self._cache:
                return self._cache[k]
        data = self.provider.synth(text, voice)
        with self._lock:
            if len(self._cache) >= self._max:
                self._cache.pop(next(iter(self._cache)))
            self._cache[k] = data
        return data

    def warm(self, phrases: List[str], voice: Optional[str] = None) -> None:
        for p in phrases:
            try:
                self.get(p, voice)
            except Exception as e:
                logger.warning(f"phrase cache warm failed for {p!r}: {e}")


# ---------------------------------------------------------------------------
# Streaming TTS orchestrator
# ---------------------------------------------------------------------------


class StreamingTTS:
    """Token stream -> sentences -> synth queue -> player callback.

    ``on_audio(chunk)`` is called (on a worker thread) as soon as each
    sentence's audio is ready. ``first_audio_latency_s`` measures
    speak() call -> first on_audio (plan target <= 300 ms for short
    replies; measured, not guaranteed — depends on the provider).
    """

    def __init__(
        self,
        provider: TTSProvider,
        on_audio: Callable[[AudioChunk], None],
        cache: Optional[PhraseCache] = None,
        max_queue: int = 8,
    ) -> None:
        self.provider = provider
        self.on_audio = on_audio
        self.cache = cache
        self._queue: "queue.Queue[AudioChunk]" = queue.Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self.first_audio_latency_s: Optional[float] = None
        self._t0: float = 0.0

    def speak_stream(self, tokens: Iterator[str], voice: Optional[str] = None) -> None:
        """Consume tokens; synth+emit per sentence. Blocks until done."""
        self._t0 = time.monotonic()
        self.first_audio_latency_s = None
        splitter = SentenceSplitter()
        idx = 0

        def _emit(text: str) -> None:
            nonlocal idx
            data = self._cached_synth(text, voice)
            if data is None:
                return
            chunk = AudioChunk(data=data, index=idx, text=text, engine=self.provider.name)
            idx += 1
            if self.first_audio_latency_s is None:
                self.first_audio_latency_s = time.monotonic() - self._t0
            self._queue.put(chunk)
            self.on_audio(chunk)

        try:
            for tok in tokens:
                if self._stop.is_set():
                    break
                for sent in splitter.feed(tok):
                    _emit(sent)
            for sent in splitter.flush():
                _emit(sent)
        finally:
            self._stop.clear()

    def _cached_synth(self, text: str, voice: Optional[str]) -> Optional[bytes]:
        try:
            if self.cache:
                return self.cache.get(text, voice)
            return self.provider.synth(text, voice)
        except Exception as e:
            logger.warning(f"TTS synth failed, skipping sentence: {e}")
            return None

    def stop(self) -> None:
        self._stop.set()


_TTS_ENGINES: Dict[str, type] = {
    "edge": EdgeTTSEngine,
    "rumik": RumikTTSEngine,
    "pyttsx3": Pyttsx3Engine,
}


def list_tts_engines() -> List[str]:
    names = sorted(_TTS_ENGINES)
    # xtts registers itself on import (optional extra).
    try:
        import jarvis.voice.tts_xtts  # noqa: F401

        names.append("xtts")
    except ImportError:
        pass
    return sorted(set(names))
