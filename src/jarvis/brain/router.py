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

    def __init__(self, reflex: Optional[ReflexMatcher] = None,
                 agent=None) -> None:
        self.reflex = reflex or ReflexMatcher()
        self._agent = agent  # lazy: reflex-only turns never init the LLM

    def _get_agent(self):
        if self._agent is None:
            from jarvis.brain.agent import AIAgent
            self._agent = AIAgent()
        return self._agent

    def handle(self, text: str) -> str:
        hit = self.reflex.match(text)
        taken = hit is not None and hit.confidence >= REFLEX_CONFIDENCE
        self.reflex.stats.record(hit.rule_id if taken else None)
        if taken:
            logger.debug("reflex hit: %s (conf %.2f)",
                         hit.rule_id, hit.confidence)
            return self._run_reflex(hit)
        return self._get_agent().process(text)

    def _run_reflex(self, hit: ReflexHit) -> str:
        # Pure compute / reply-only rules: no tool call at all.
        if hit.compute or not hit.tool:
            return hit.render_reply(self.reflex._rng)

        from jarvis.policy.command_policy import CONFIRM, DENY
        from jarvis.tools.actions import run_action

        args = hit.render_args()
        verdict, result = run_action(hit.tool, args)
        if verdict == CONFIRM:
            # The agent owns the confirmation state machine.
            return self._get_agent().request_confirmation(hit.tool, args)
        if verdict == DENY:
            return result  # the block reason
        # ALLOW: prefer the rule's reply template, else the tool's output.
        reply = hit.render_reply(self.reflex._rng)
        return reply if reply else result
