"""Model router + cost control (Master Plan Task 4.2).

Tiers:
    T0 Reflex — no LLM (Task 2.6 reflex match)
    T1 Fast   — intent -> single tool, short Q&A
    T2 Strong — planning, multi-step, coding, long reasoning
    T3 Local  — offline / privacy-mode / provider down (Ollama)

Routing is rule-based first (length, keywords, tool-count heuristics);
every decision is logged. Model names come from config, never hard-coded
here (F-24: model bake-off picks the winners; see evals/).

Cost guard: daily token / INR budgets; on breach, downgrade to T1/T3 and
notify the user. Semantic cache: short-TTL cache for repeated READ-only
factual answers (never for tool calls).
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class Tier(IntEnum):
    T0_REFLEX = 0
    T1_FAST = 1
    T2_STRONG = 2
    T3_LOCAL = 3


@dataclass
class TierDecision:
    tier: Tier
    model: str
    reason: str


# Signals that push toward T2 (strong): planning, code, multi-step.
_T2_KEYWORDS = re.compile(
    r"(?i)\b(plan|steps|compare|analyze|analyse|debug|code|script|"
    r"explain in detail|research|strategy|design)\b"
)


def _looks_multi_tool(text: str) -> bool:
    # "aur" / "and" joining two imperatives, or explicit sequencing.
    t = text.lower()
    return bool(re.search(r"\b(aur|and|then|phir|uske baad)\b", t) and len(t.split()) > 6)


class ModelRouter:
    """Rule-based tier router. Model names resolve from config at call time."""

    def __init__(self, settings=None) -> None:
        self.settings = settings

    def _model_for(self, tier: Tier) -> str:
        s = self.settings
        if tier == Tier.T1_FAST:
            return getattr(getattr(s, "brain", None), "t1_model", "") or "fast-default"
        if tier == Tier.T2_STRONG:
            return getattr(getattr(s, "brain", None), "t2_model", "") or getattr(
                getattr(s, "brain", None), "hf_model", "strong-default"
            )
        if tier == Tier.T3_LOCAL:
            return getattr(getattr(s, "brain", None), "t3_model", "") or "ollama-default"
        return "reflex"

    def route(self, utterance: str, ctx: Optional[Dict[str, Any]] = None) -> TierDecision:
        ctx = ctx or {}
        text = (utterance or "").strip()

        # T3: offline / privacy / provider down — explicit, never guessed.
        if ctx.get("offline") or ctx.get("privacy_mode") or ctx.get("provider_down"):
            d = TierDecision(
                Tier.T3_LOCAL,
                self._model_for(Tier.T3_LOCAL),
                "offline/privacy/provider-down -> local",
            )
            logger.info("model_router: %s", d)
            return d
        # T2: strong signals.
        if _T2_KEYWORDS.search(text) or _looks_multi_tool(text) or len(text) > 220:
            d = TierDecision(
                Tier.T2_STRONG, self._model_for(Tier.T2_STRONG), "planning/code/multi-step signal"
            )
            logger.info("model_router: %s", d)
            return d
        # T1: everything else that needs the LLM. (T0 is decided by the
        # reflex matcher upstream in brain/router.py.)
        d = TierDecision(
            Tier.T1_FAST, self._model_for(Tier.T1_FAST), "short utterance, single intent"
        )
        logger.info("model_router: %s", d)
        return d


# ---------------------------------------------------------------------------
# Cost guard
# ---------------------------------------------------------------------------


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_inr: float = 0.0


class CostGuard:
    """Daily budgets; on breach, downgrade + notify.

    Budgets come from config (brain.daily_token_budget,
    brain.daily_cost_inr_budget; 0 = unlimited).
    """

    def __init__(self, settings=None, notify: Optional[Callable[[str], None]] = None) -> None:
        self.settings = settings
        self.notify = notify or (lambda msg: logger.warning("cost guard: %s", msg))
        self._day = time.strftime("%Y-%m-%d")
        self.used = Usage()
        self._breached = False

    def _budgets(self) -> Tuple[int, float]:
        brain = getattr(self.settings, "brain", None)
        return (
            int(getattr(brain, "daily_token_budget", 0) or 0),
            float(getattr(brain, "daily_cost_inr_budget", 0) or 0),
        )

    def _roll_day(self) -> None:
        today = time.strftime("%Y-%m-%d")
        if today != self._day:
            self._day, self.used, self._breached = today, Usage(), False

    def record(self, usage: Usage) -> None:
        self._roll_day()
        self.used.prompt_tokens += usage.prompt_tokens
        self.used.completion_tokens += usage.completion_tokens
        self.used.cost_inr += usage.cost_inr
        tok_budget, inr_budget = self._budgets()
        total_tok = self.used.prompt_tokens + self.used.completion_tokens
        breached = (tok_budget and total_tok >= tok_budget) or (
            inr_budget and self.used.cost_inr >= inr_budget
        )
        if breached and not self._breached:
            self._breached = True
            self.notify("Daily AI budget khatm ho gaya — ab fast/local models use honge.")

    @property
    def breached(self) -> bool:
        self._roll_day()
        return self._breached

    def effective_tier(self, tier: Tier) -> Tier:
        """Downgrade T2 -> T1 when the budget is breached."""
        if self._breached and tier == Tier.T2_STRONG:
            return Tier.T1_FAST
        return tier


# ---------------------------------------------------------------------------
# Semantic cache (READ-only answers, short TTL)
# ---------------------------------------------------------------------------


class SemanticCache:
    """Caches repeated factual answers. Never caches tool calls."""

    def __init__(self, ttl_s: float = 600.0, max_entries: int = 200) -> None:
        self.ttl_s = ttl_s
        self.max_entries = max_entries
        self._cache: Dict[str, Tuple[str, float]] = {}

    @staticmethod
    def _key(text: str) -> str:
        norm = re.sub(r"\s+", " ", (text or "").strip().lower())
        return hashlib.sha256(norm.encode()).hexdigest()

    def get(self, query: str) -> Optional[str]:
        k = self._key(query)
        hit = self._cache.get(k)
        if hit is None:
            return None
        answer, ts = hit
        if time.time() - ts > self.ttl_s:
            del self._cache[k]
            return None
        logger.debug("semantic cache hit")
        return answer

    def put(self, query: str, answer: str, involved_tools: bool) -> None:
        """Store only pure answers (no tool calls involved)."""
        if involved_tools:
            return
        if len(self._cache) >= self.max_entries:
            oldest = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest]
        self._cache[self._key(query)] = (answer, time.time())
