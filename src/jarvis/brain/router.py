"""Utterance router — System-1 (reflex) vs System-2 (LLM) (Task 2.6).

``utterance → reflex.match()?``
  * yes, confidence ≥ 0.85 → policy-gated tool call → reply template
  * no                       → LLM agent loop (provider chain)

Reflex tool calls go through :py:func:`run_action` — the same policy
gate the LLM path uses. There is no bypass: a reflex hit for a
destructive/system action still asks for confirmation or gets denied.
"""

from __future__ import annotations

import logging
from typing import Optional

from jarvis.brain.reflex import ReflexHit, ReflexMatcher

logger = logging.getLogger(__name__)

REFLEX_CONFIDENCE = 0.85


class Router:
    """Routes utterances to the reflex layer or the LLM agent."""

    def __init__(
        self, reflex: Optional[ReflexMatcher] = None, agent=None, metrics=None, bus=None
    ) -> None:
        self.reflex = reflex or ReflexMatcher()
        self._agent = agent  # lazy: reflex-only turns never init the LLM
        self._metrics = metrics  # None -> default MetricsRecorder
        if bus is None:
            from jarvis.core.events import get_bus

            bus = get_bus()
        self.bus = bus

    def _get_agent(self):
        if self._agent is None:
            from jarvis.brain.agent import AIAgent

            self._agent = AIAgent()
        return self._agent

    def _get_metrics(self):
        if self._metrics is None:
            from jarvis.core.metrics import MetricsRecorder

            self._metrics = MetricsRecorder()
        return self._metrics

    def handle(self, text: str) -> str:
        """Route one utterance; trace it and record stage timings."""
        from jarvis.core.events import UtteranceFinal
        from jarvis.core.logging import StageTimer, new_trace_id, set_trace_id

        trace = new_trace_id()
        set_trace_id(trace)
        self.bus.emit(UtteranceFinal(trace=trace, text=text))
        path, provider, degraded, error = "llm", "", False, ""
        st = StageTimer()
        try:
            with st:
                with st.stage("reflex_match"):
                    hit = self.reflex.match(text)
                taken = hit is not None and hit.confidence >= REFLEX_CONFIDENCE
                self.reflex.stats.record(hit.rule_id if taken else None)
                with st.stage("run"):
                    if taken:
                        path = "reflex"
                        provider = "reflex"
                        logger.debug("reflex hit: %s (conf %.2f)", hit.rule_id, hit.confidence)
                        return self._run_reflex(hit)
                    out = self._get_agent().process(text)
                    res = getattr(self._get_agent(), "last_chain_result", None)
                    if res is not None:
                        provider = res.provider_name
                        degraded = res.degraded
                    return out
        except Exception as e:
            error = str(e)
            raise
        finally:
            try:
                self._get_metrics().record(
                    trace, path, st.timings, provider=provider, degraded=degraded, error=error
                )
            except Exception:
                logger.exception("metrics record failed")

    def _run_reflex(self, hit: ReflexHit) -> str:
        # Pure compute / reply-only rules: no tool call at all.
        if hit.compute or not hit.tool:
            return hit.render_reply(self.reflex._rng)

        from jarvis.core.events import ToolFinished, ToolRequested
        from jarvis.core.logging import get_trace_id
        from jarvis.policy.command_policy import CONFIRM, DENY
        from jarvis.tools.actions import run_action

        args = hit.render_args()
        trace = get_trace_id()
        self.bus.emit(ToolRequested(trace=trace, tool=hit.tool, args=args))
        verdict, result = run_action(hit.tool, args)
        if verdict == CONFIRM:
            # The agent owns the confirmation state machine.
            self.bus.emit(
                ToolFinished(trace=trace, tool=hit.tool, ok=False, result="confirmation requested")
            )
            return self._get_agent().request_confirmation(hit.tool, args)
        if verdict == DENY:
            self.bus.emit(ToolFinished(trace=trace, tool=hit.tool, ok=False, result=result))
            return result  # the block reason
        # ALLOW: prefer the rule's reply template, else the tool's output.
        reply = hit.render_reply(self.reflex._rng)
        self.bus.emit(
            ToolFinished(trace=trace, tool=hit.tool, ok=True, result=reply if reply else result)
        )
        return reply if reply else result
