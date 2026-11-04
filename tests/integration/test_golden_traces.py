"""Golden-trace tests (Master Plan Task 2.8.3).

One utterance -> the exact expected event sequence, end to end, on
fakes only: no mic, no network, no OS side effects. This is the
"voice -> tool -> reply" flow the plan requires to run in CI.
"""

import random
import sys
from unittest import mock
from unittest.mock import MagicMock

# Stub Windows-only modules so the imports stay headless.
for _mod in ("pyautogui",):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))

import pytest  # noqa: E402

from jarvis.brain.reflex import ReflexMatcher, ReflexStats  # noqa: E402
from jarvis.brain.router import Router  # noqa: E402
from jarvis.core.events import Bus  # noqa: E402
from jarvis.core.metrics import MetricsRecorder  # noqa: E402
from tests.fakes import FakeLLM, FakeMic, FakeOS, FakeSTT  # noqa: E402


@pytest.fixture()
def bus():
    return Bus()


@pytest.fixture()
def seen(bus):
    events = []
    bus.on_all(events.append)
    return events


@pytest.fixture()
def router(bus, tmp_path):
    stats = ReflexStats(path=str(tmp_path / "stats.json"))
    metrics = MetricsRecorder(metrics_dir=str(tmp_path / "metrics"))
    return Router(
        bus=bus,
        reflex=ReflexMatcher(stats=stats, rng=random.Random(0)),
        agent=mock.MagicMock(),
        metrics=metrics,
    )


def _types(seen):
    return [type(e).__name__ for e in seen]


# ---------------------------------------------------------------------------


def test_golden_reflex_tool_trace(router, seen):
    """'search google for weather' -> UtteranceFinal, ToolRequested,
    ToolFinished; web_search (READ) auto-allows at default autonomy."""
    with FakeOS() as fake_os:
        reply = router.handle("search google for weather")
    assert _types(seen) == ["UtteranceFinal", "ToolRequested", "ToolFinished"]
    assert seen[0].text == "search google for weather"
    assert seen[1].tool == "web_search"
    assert seen[1].args == {"query": "weather"}
    assert seen[2].tool == "web_search" and seen[2].ok is True
    assert fake_os.actions == [("web_search", {"query": "weather"})]
    assert reply == "Searching Google for weather"


def test_golden_reflex_confirm_trace(router, seen):
    """Reversible actions ask for confirmation: ToolFinished(ok=False),
    then the agent owns the confirmation."""
    agent = router._agent
    agent.request_confirmation.return_value = "confirm?"
    with FakeOS() as fake_os:
        reply = router.handle("open youtube")
    assert _types(seen) == ["UtteranceFinal", "ToolRequested", "ToolFinished"]
    assert seen[2].ok is False
    assert fake_os.actions == []  # nothing executed before confirmation
    agent.request_confirmation.assert_called_once_with(
        "open_website", {"url_or_name": "https://www.youtube.com"}
    )
    assert reply == "confirm?"


def test_golden_compute_trace(router, seen):
    """Pure compute rules emit no tool events."""
    assert router.handle("calculate 6 * 7") == "6 * 7 is 42"
    assert _types(seen) == ["UtteranceFinal"]


def test_golden_llm_fallback_trace(router, seen):
    """Unrecognized utterance -> UtteranceFinal, AgentThinking, LLM reply."""
    from jarvis.core.events import AgentThinking

    def _process(text):
        router.bus.emit(AgentThinking(trace="t", status="Thinking..."))
        return "llm reply"

    router._agent.process.side_effect = _process
    assert router.handle("xqzw blorpt fnord") == "llm reply"
    assert _types(seen) == ["UtteranceFinal", "AgentThinking"]


def test_golden_voice_to_tool_to_reply(router, seen, tmp_path):
    """FakeMic (wav) -> FakeSTT (transcript) -> Router -> FakeOS.

    The whole voice pipeline with no microphone and no network.
    """
    wav_path = FakeMic.synth_tone(seconds=0.3)
    try:
        with FakeMic(wav_path) as mic:
            audio = b"".join(mic.frames())
        assert mic.frames_read > 0
        stt = FakeSTT(["search google for weather"])
        text = stt.transcribe(audio)
        assert stt.calls[0]["bytes"] == len(audio)
        with FakeOS() as fake_os:
            reply = router.handle(text)
    finally:
        import os

        os.remove(wav_path)
    assert reply == "Searching Google for weather"
    assert fake_os.action_names() == ["web_search"]
    assert _types(seen) == ["UtteranceFinal", "ToolRequested", "ToolFinished"]


def test_golden_llm_tool_call_trace(bus, seen, tmp_path):
    """LLM tool-call round-trip on a FakeLLM: the agent's own
    ToolRequested/ToolFinished events fire in order."""
    from jarvis.brain.agent import AIAgent

    fake = FakeLLM(
        script=[
            {
                "text": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "name": "open_website",
                        "args": {"url_or_name": "https://example.com"},
                    }
                ],
            },
            {"text": "done"},
        ]
    )
    agent = AIAgent.__new__(AIAgent)
    agent.bus = bus
    agent.session_id = "golden"
    agent.temperature = 0.3
    agent.conversation_history = []
    agent.max_history = 10
    agent.tool_definitions = []
    agent._get_system_prompt = lambda memory_context="": "sys"
    # Real _dispatch_tool_call (emits ToolRequested/Finished); stub only the
    # policy decision, the executor and the audit sink.
    agent._decide = lambda name, args, ctx=None: ("ALLOW", "test allow")
    agent._execute_tool = lambda name, args: "tool-ok"
    agent._audit = lambda *a, **k: None
    agent._breaker = mock.MagicMock()
    agent._breaker.allow.return_value = True
    agent._rate_limiter = mock.MagicMock()
    agent._rate_limiter.allow.return_value = True
    agent._rate_limiter.over_budget.return_value = False
    agent.tainted = False
    agent.rate_limited = False
    agent._sanitize_for_prompt = lambda n, a, r: r
    agent._notify_status = lambda m: None
    agent._chain_complete = lambda messages, tools=None: fake.complete(messages, tools=tools)
    reply = AIAgent._call_llm_flow(agent, "open example")
    assert reply == "done"
    names = _types(seen)
    assert "ToolRequested" in names and "ToolFinished" in names
    assert names.index("ToolRequested") < names.index("ToolFinished")
    # the tool call the fake LLM requested is the one that ran
    req = next(e for e in seen if type(e).__name__ == "ToolRequested")
    assert req.tool == "open_website"
    assert req.args == {"url_or_name": "https://example.com"}
