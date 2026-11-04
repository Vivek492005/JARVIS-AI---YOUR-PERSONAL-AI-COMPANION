"""Provider chain manager: retry + fallback + circuit breaker (Task 2.5.3).

Policy per provider attempt:
  * skip when its circuit breaker is OPEN (5 consecutive failures → 60 s
    open, per the plan; reuses :py:class:`jarvis.core.safety.CircuitBreaker`),
  * on generic failure: retry with exponential backoff + jitter, max 2
    retries (3 attempts total),
  * on quota exhaustion (HTTP 429): NO retry — straight to the next
    provider,
  * when every cloud provider is exhausted: the local heuristic provider
    (Task 2.5.5), flagged ``degraded=True``.

Honest degradation (Task 2.5.4): every fallback fires ``on_degraded``
with a plain-language notice *as it happens* — the agent surfaces these
via status callback + ``StatusChanged`` event instead of silently
dropping in quality.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from jarvis.brain.providers.base import Completion, LLMProvider
from jarvis.core.errors import ProviderError, QuotaExhaustedError
from jarvis.core.safety import CircuitBreaker

logger = logging.getLogger(__name__)


@dataclass
class ChainResult:
    completion: Completion
    degraded: bool = False
    notices: List[str] = field(default_factory=list)
    provider_name: str = ""


class ProviderChain:
    """Ordered providers with resilience policy."""

    def __init__(
        self,
        providers: List[LLMProvider],
        local_provider: Optional[LLMProvider] = None,
        on_degraded: Optional[Callable[[str], None]] = None,
        max_retries: int = 2,
        base_backoff_s: float = 0.5,
        max_failures: int = 5,
        cooldown_s: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
        rng: Optional[random.Random] = None,
    ) -> None:
        self._providers = list(providers)
        self._local = local_provider
        self._on_degraded = on_degraded
        self._max_retries = max_retries
        self._base_backoff = base_backoff_s
        self._sleep = sleep
        # Jitter only — not cryptographic; stdlib random is fine.
        self._rng = rng or random.Random()  # noqa: S311
        self._breakers: Dict[str, CircuitBreaker] = {
            p.name: CircuitBreaker(max_failures=max_failures, cooldown_s=cooldown_s)
            for p in providers
        }

    @property
    def provider_names(self) -> List[str]:
        return [p.name for p in self._providers]

    def _notice(self, msg: str, notices: List[str]) -> None:
        notices.append(msg)
        logger.warning("provider chain: %s", msg)
        if self._on_degraded is not None:
            try:
                self._on_degraded(msg)
            except Exception:
                logger.exception("on_degraded callback crashed")

    def _backoff(self, attempt: int) -> float:
        # Exponential backoff + jitter: 0.5, 1.0, 2.0 … + up to 250 ms.
        return self._base_backoff * (2**attempt) + self._rng.uniform(0, 0.25)

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
    ) -> ChainResult:
        notices: List[str] = []
        fell_back = False

        for provider in self._providers:
            breaker = self._breakers[provider.name]
            if not breaker.allow():
                logger.debug("provider chain: skipping %s (circuit open)", provider.name)
                continue
            attempt = 0
            while True:
                try:
                    comp = provider.complete(messages, tools=tools, temperature=temperature)
                except QuotaExhaustedError:
                    # Quota wall: retrying is pointless — next provider.
                    breaker.record_failure()
                    self._notice(f"{provider.name}: quota exhausted — switching provider", notices)
                    fell_back = True
                    break
                except Exception as e:
                    if attempt < self._max_retries:
                        delay = self._backoff(attempt)
                        logger.debug(
                            "provider chain: %s failed (attempt %d), retrying in %.2fs: %s",
                            provider.name,
                            attempt + 1,
                            delay,
                            e,
                        )
                        self._sleep(delay)
                        attempt += 1
                        continue
                    breaker.record_failure()
                    self._notice(f"{provider.name} unreachable ({e}) — switching provider", notices)
                    fell_back = True
                    break
                breaker.record_success()
                return ChainResult(
                    completion=comp,
                    degraded=fell_back,
                    notices=notices,
                    provider_name=provider.name,
                )

        # Every cloud provider exhausted → honest local mode.
        if self._local is not None:
            self._notice(
                "Cloud brain unreachable — local mode (limited capabilities, no cloud LLM)", notices
            )
            comp = self._local.complete(messages, tools=tools, temperature=temperature)
            comp.provider = self._local.name
            return ChainResult(
                completion=comp, degraded=True, notices=notices, provider_name=self._local.name
            )

        raise ProviderError(
            f"all providers failed: {', '.join(self.provider_names)}; notices: {'; '.join(notices)}"
        )
