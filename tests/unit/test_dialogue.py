"""Tests for Task 3.8: dialogue state machine + earcons."""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from jarvis.voice.dialogue import (  # noqa: E402
    DialogueMachine,
    DialogueState,
    NullEarconPlayer,
)


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def _machine(**kw):
    clock = _Clock()
    earcons = NullEarconPlayer()
    events = []
    fillers = []
    m = DialogueMachine(earcons=earcons, bus_emit=events.append,
                        speak_filler=fillers.append, clock=clock)
    return m, clock, earcons, events, fillers


def test_happy_path_transitions():
    m, clock, earcons, events, _ = _machine()
    assert m.to(DialogueState.LISTENING)
    assert m.to(DialogueState.THINKING)
    assert m.to(DialogueState.SPEAKING)
    assert m.to(DialogueState.IDLE)
    assert m.state == DialogueState.IDLE
    assert earcons.played == ["listening", "thinking", "speaking", "idle"]
    assert len(events) == 4  # one StatusChanged per transition
    assert len(m.history) == 4


def test_illegal_transition_rejected():
    m, *_ = _machine()
    assert not m.to(DialogueState.SPEAKING)  # IDLE -> SPEAKING illegal
    assert m.state == DialogueState.IDLE


def test_confirming_loop():
    m, *_ = _machine()
    assert m.to(DialogueState.LISTENING)
    assert m.to(DialogueState.THINKING)
    assert m.to(DialogueState.CONFIRMING)
    assert m.to(DialogueState.THINKING)  # confirmed -> think again
    assert m.to(DialogueState.IDLE)


def test_any_to_idle_on_error():
    m, *_ = _machine()
    assert m.to(DialogueState.LISTENING)
    assert m.to(DialogueState.IDLE)  # cancel path always legal


def test_filler_only_after_threshold():
    m, clock, _, _, fillers = _machine()
    m.to(DialogueState.LISTENING)
    m.to(DialogueState.THINKING)
    clock.advance(0.5)
    assert not m.maybe_filler()
    assert fillers == []
    clock.advance(1.0)  # 1.5 s total > 1.2 s
    assert m.maybe_filler()
    assert fillers == ["ek second…"]
    assert not m.maybe_filler()  # one-shot


def test_filler_resets_on_new_think():
    m, clock, _, _, fillers = _machine()
    m.to(DialogueState.LISTENING)
    m.to(DialogueState.THINKING)
    clock.advance(2.0)
    assert m.maybe_filler()
    m.to(DialogueState.IDLE)
    m.to(DialogueState.LISTENING)
    m.to(DialogueState.THINKING)
    assert fillers == ["ek second…"]  # not yet re-spoken
    clock.advance(2.0)
    assert m.maybe_filler()
    assert len(fillers) == 2
