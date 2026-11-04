"""OpenAI-compatible LLM adapters (Master Plan Task 2.5).

One adapter class covers every OpenAI-compatible endpoint; the named
subclasses just bind the plan's providers (HuggingFace router, DeepSeek,
Ollama) to their URLs, models and env-var conventions.

Timeouts follow the plan: connect 3 s, first-token/read 6 s.
HTTP 429 (or the OpenAI ``RateLimitError``) is translated to
:py:class:`QuotaExhaustedError` so the chain manager can skip straight
to the next provider instead of retrying a quota wall.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from jarvis.brain.providers.base import Completion, ToolCall
from jarvis.core.errors import ProviderError, QuotaExhaustedError

logger = logging.getLogger(__name__)

# Plan §2.5: per-provider timeout — connect 3 s, first-token 6 s.
DEFAULT_TIMEOUT = httpx.Timeout(connect=3.0, read=6.0, write=6.0, pool=3.0)


def _is_quota_error(exc: Exception) -> bool:
    """True for HTTP 429 / OpenAI RateLimitError / quota messages."""
    if getattr(exc, "status_code", None) == 429:
        return True
    try:
        from openai import RateLimitError

        if isinstance(exc, RateLimitError):
            return True
    except ImportError:
        pass
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "quota" in msg


class OpenAICompatibleProvider:
    """Any OpenAI-compatible chat endpoint (plan's ``OpenAICompatible``)."""

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        client: Any = None,
    ) -> None:
        from openai import OpenAI  # lazy: keeps import cost off module load

        self._name = name
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._client = client or OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return self._model

    @property
    def raw_client(self):
        """The underlying ``openai.OpenAI`` client (back-compat for tests)."""
        return self._client

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
    ) -> Completion:
        kwargs: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            if _is_quota_error(e):
                raise QuotaExhaustedError(f"{self._name}: {e}") from e
            raise ProviderError(f"{self._name}: {e}") from e

        message = response.choices[0].message
        calls: List[ToolCall] = []
        for tc in message.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            calls.append(ToolCall(id=tc.id, name=tc.function.name, args=args))
        return Completion(
            text=(message.content or "").strip(),
            tool_calls=calls,
            provider=self._name,
            raw=response,
        )

    def health(self) -> bool:
        """Cheap ping: the provider's /models endpoint, 2 s budget.

        Any non-5xx (including 401 without a key) means "reachable".
        """
        try:
            r = httpx.get(f"{self._base_url}/models", timeout=2.0)
            return r.status_code < 500
        except Exception:
            return False


class HuggingFaceRouter(OpenAICompatibleProvider):
    """Primary cloud brain: Qwen 2.5 72B via the HF router."""

    def __init__(
        self, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None, **kw
    ) -> None:
        super().__init__(
            "huggingface",
            api_key,
            base_url or os.getenv("HUGGINGFACE_BASE_URL", "https://router.huggingface.co/v1"),
            model or os.getenv("HUGGINGFACE_MODEL", "Qwen/Qwen2.5-72B-Instruct"),
            **kw,
        )


class DeepSeek(OpenAICompatibleProvider):
    """Backup cloud brain: DeepSeek chat."""

    def __init__(
        self, api_key: str, model: Optional[str] = None, base_url: Optional[str] = None, **kw
    ) -> None:
        super().__init__(
            "deepseek",
            api_key,
            base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            **kw,
        )


class Ollama(OpenAICompatibleProvider):
    """Local brain: Ollama (OpenAI-compatible /v1 endpoint)."""

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None, **kw) -> None:
        super().__init__(
            "ollama",
            "ollama",  # key unused locally
            base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
            **kw,
        )
