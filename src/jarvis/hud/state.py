"""HUD state machine (Task 7.2).

Derives the single active HUD state from bus events. The web UI renders whatever
state this machine reports — no polling, no guessing. Illegal transitions are
ignored (logged) so a stray/duplicate event can never corrupt the display.

States: idle, listening, thinking, speaking, confirming, error.
See docs/HUD_SPEC.md for the state -> visual mapping.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# The six HUD states from the design spec.
IDLE = "idle"
LISTENING = "listening"
THINKING = "thinking"
SPEAKING = "speaking"
CONFIRMING = "confirming"
ERROR = "error"

STATES = (IDLE, LISTENING, THINKING, SPEAKING, CONFIRMING, ERROR)

# event type name -> (from-states, to-state). Absent event = no state change.
_TRANSITIONS: Dict[str, tuple] = {
    "WakeDetected": ((IDLE, ERROR), LISTENING),
    "UtterancePartial": ((LISTENING,), LISTENING),
    "UtteranceFinal": ((LISTENING,), THINKING),
    "AgentThinking": ((THINKING, LISTENING, IDLE), THINKING),
    "ToolRequested": ((THINKING,), THINKING),
    "ToolFinished": ((THINKING,), THINKING),
    "ConfirmationRequested": ((THINKING,), CONFIRMING),
    "ConfirmationAnswered": ((CONFIRMING,), THINKING),
    "SpeechStarted": ((THINKING, IDLE, LISTENING), SPEAKING),
    "SpeechStopped": ((SPEAKING,), IDLE),
    "Interrupt": ((SPEAKING, LISTENING, THINKING), IDLE),
    "Error": ((IDLE, LISTENING, THINKING, SPEAKING, CONFIRMING), ERROR),
}


@dataclass
class TimelineEntry:
    """One row in the HUD action timeline."""
    label: str
    ok: Optional[bool] = None  # None = in-progress
    detail: str = ""


@dataclass
class TranscriptTurn:
    who: str  # "user" | "jarvis"
    text: str
    live: bool = False  # True while a partial is still streaming


class HUDStateMachine:
    """Event-driven HUD state + transcript + timeline model.

    Feed it bus events (or their `event_to_dict` form); read `state`,
    `transcript`, `timeline` to render. `subscribe()` gets a callback on
    every accepted change (the WS fan-out uses this).
    """

    def __init__(self) -> None:
        self.state: str = IDLE
        self.transcript: List[TranscriptTurn] = []
        self.timeline: List[TimelineEntry] = []
        self.confirm_card: Optional[Dict[str, Any]] = None
        self.error_info: Optional[Dict[str, str]] = None
        self.audio_level: float = 0.0
        self._subs: List[Callable[[str, Dict[str, Any]], None]] = []

    # -- subscription -----------------------------------------------------
    def subscribe(self, cb: Callable[[str, Dict[str, Any]], None]) -> None:
        self._subs.append(cb)

    def _emit(self, kind: str, payload: Dict[str, Any]) -> None:
        for cb in list(self._subs):
            try:
                cb(kind, payload)
            except Exception:  # never let the HUD break the agent
                logger.exception("hud subscriber failed")

    # -- event intake -----------------------------------------------------
    def on_event(self, event: Any) -> str:
        """Accept a bus Event or an event_to_dict() mapping. Returns state."""
        if isinstance(event, dict):
            etype = event.get("type", "")
            data = event
        else:
            etype = type(event).__name__
            data = {"type": etype}
            for f in getattr(event, "__dataclass_fields__", {}):
                if f not in ("trace", "ts"):
                    data[f] = getattr(event, f)

        self._handle(etype, data)
        return self.state

    def _set_state(self, new: str, etype: str) -> None:
        if new == self.state:
            return
        old = self.state
        self.state = new
        logger.debug("hud %s -> %s (%s)", old, new, etype)
        self._emit("state", {"from": old, "to": new, "event": etype})

    def _handle(self, etype: str, data: Dict[str, Any]) -> None:
        # --- content updates (independent of state) ---
        if etype == "UtterancePartial":
            self._upsert_live_turn("user", str(data.get("text", "")))
        elif etype == "UtteranceFinal":
            self._commit_turn("user", str(data.get("text", "")))
        elif etype == "SpeechStarted":
            self._commit_turn("jarvis", str(data.get("text", "")))
        elif etype == "ToolRequested":
            tool = str(data.get("tool", "?"))
            self.timeline.append(TimelineEntry(label=f"{tool}…"))
            self._emit("timeline", {"action": "add", "label": f"{tool}…"})
        elif etype == "ToolFinished":
            tool = str(data.get("tool", "?"))
            ok = bool(data.get("ok", True))
            self._finish_timeline_entry(tool, ok)
        elif etype == "ConfirmationRequested":
            self.confirm_card = {
                "tool": str(data.get("tool", "?")),
                "question": str(data.get("question", "")),
            }
            self._emit("confirm", dict(self.confirm_card))
        elif etype == "ConfirmationAnswered":
            self.confirm_card = None
            self._emit("confirm", {"dismissed": True})
        elif etype == "Error":
            self.error_info = {
                "where": str(data.get("where", "")),
                "message": str(data.get("message", "")),
            }
        elif etype == "AudioLevel":  # pushed by the mic pipeline, not a bus Event
            try:
                self.audio_level = max(0.0, min(1.0, float(data.get("level", 0.0))))
            except (TypeError, ValueError):
                pass
            return  # never changes state

        # --- state transition ---
        rule = _TRANSITIONS.get(etype)
        if rule is None:
            return
        allowed_from, to_state = rule
        if self.state in allowed_from:
            # leaving error clears the banner; leaving confirming clears card
            if self.state == ERROR and to_state != ERROR:
                self.error_info = None
            self._set_state(to_state, etype)
        else:
            logger.debug("hud ignored %s in state %s", etype, self.state)

    # -- transcript helpers -----------------------------------------------
    def _upsert_live_turn(self, who: str, text: str) -> None:
        if self.transcript and self.transcript[-1].live and self.transcript[-1].who == who:
            self.transcript[-1].text = text
        else:
            self.transcript.append(TranscriptTurn(who=who, text=text, live=True))
        self._emit("transcript", {"who": who, "text": text, "live": True})

    def _commit_turn(self, who: str, text: str) -> None:
        if self.transcript and self.transcript[-1].live and self.transcript[-1].who == who:
            self.transcript[-1].text = text
            self.transcript[-1].live = False
        else:
            self.transcript.append(TranscriptTurn(who=who, text=text, live=False))
        self._emit("transcript", {"who": who, "text": text, "live": False})

    def _finish_timeline_entry(self, tool: str, ok: bool) -> None:
        for entry in reversed(self.timeline):
            if entry.ok is None and entry.label.startswith(tool):
                entry.ok = ok
                entry.label = f"{tool} {'✓' if ok else '✗'}"
                self._emit("timeline", {"action": "finish", "label": entry.label,
                                        "ok": ok})
                return
        # No matching in-progress entry (e.g. restarted) — still show it.
        self.timeline.append(TimelineEntry(label=f"{tool} {'✓' if ok else '✗'}",
                                           ok=ok))

    # -- snapshot for new clients ------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "audio_level": self.audio_level,
            "transcript": [{"who": t.who, "text": t.text, "live": t.live}
                           for t in self.transcript[-50:]],
            "timeline": [{"label": e.label, "ok": e.ok} for e in self.timeline[-30:]],
            "confirm_card": self.confirm_card,
            "error": self.error_info,
        }
