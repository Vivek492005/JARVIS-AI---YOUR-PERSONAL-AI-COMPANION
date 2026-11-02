"""HUD package (Task 7.2): web UI served by jarvisd + event-driven state machine."""

from jarvis.hud.state import (
    HUDStateMachine,
    CONFIRMING,
    ERROR,
    IDLE,
    LISTENING,
    SPEAKING,
    STATES,
    THINKING,
    TimelineEntry,
    TranscriptTurn,
)

__all__ = [
    "HUDStateMachine",
    "TimelineEntry",
    "TranscriptTurn",
    "STATES",
    "IDLE",
    "LISTENING",
    "THINKING",
    "SPEAKING",
    "CONFIRMING",
    "ERROR",
]
