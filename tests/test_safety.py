"""Tests for Task 1.8: kill switch, rate limiter, circuit breaker, stop words."""

import sys
import time
from unittest import mock
from unittest.mock import MagicMock

for _mod in ("speech_recognition", "pyttsx3", "pyautogui", "pyperclip",
             "fuzzywuzzy"):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))
sys.modules["fuzzywuzzy"].fuzz = MagicMock()

import pytest  # noqa: E402

from access_os.safety import (  # noqa: E402
    CircuitBreaker,
    KillSwitch,
    RateLimiter,
    is_stop_command,
)


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------

def test_kill_switch_trigger_and_callbacks():
    ks = KillSwitch()
    calls = []
    ks.on_trigger(lambda: calls.append(1))
    assert not ks.is_triggered()
    ks.trigger("test")
    assert ks.is_triggered()
    assert calls == [1]
    ks.trigger("again")  # idempotent — callbacks run once
    assert calls == [1]
    ks.reset()
    assert not ks.is_triggered()


def test_kill_switch_hotkey_graceful_without_package():
    ks = KillSwitch()
    # 'keyboard' is not installed here -> best-effort False, no crash.
    assert ks.install_hotkey() is False


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

def test_rate_limiter_budget():
    rl = RateLimiter(max_calls=3, window_s=60)
    assert rl.allow() and rl.allow() and rl.allow()
    assert not rl.allow()
    assert rl.over_budget()
    rl.reset()
    assert rl.allow()


def test_rate_limiter_window_slides():
    rl = RateLimiter(max_calls=1, window_s=60)
    assert rl.allow()
    assert not rl.allow()
    with mock.patch("access_os.safety.time.time",
                    return_value=time.time() + 61):
        assert not rl.over_budget()
        assert rl.allow()


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

def test_breaker_trips_and_recovers():
    cb = CircuitBreaker(max_failures=3, cooldown_s=60)
    assert cb.allow()
    cb.record_failure()
    cb.record_failure()
    assert cb.allow()
    cb.record_failure()
    assert not cb.allow()
    assert cb.state == "open"
    cb.record_success()  # manual close path
    assert cb.allow()


def test_breaker_half_open_after_cooldown():
    cb = CircuitBreaker(max_failures=1, cooldown_s=60)
    cb.record_failure()
    assert cb.state == "open"
    with mock.patch("access_os.safety.time.time",
                    return_value=time.time() + 61):
        assert cb.state == "half_open"
        assert cb.allow()
        cb.record_success()
        assert cb.state == "closed"


# ---------------------------------------------------------------------------
# Stop words
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("w", ["stop", "Stop.", "ruko", "RUK JAO", "bas",
                               "bas karo", "cancel", "chup"])
def test_stop_words_match(w):
    assert is_stop_command(w)


@pytest.mark.parametrize("w", ["stop the music", "unstoppable", "",
                               "please continue", "desktop"])
def test_stop_words_no_false_positive(w):
    assert not is_stop_command(w)


# ---------------------------------------------------------------------------
# Agent wiring
# ---------------------------------------------------------------------------

@pytest.fixture()
def agent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from access_os.ai_agent import AIAgent
    a = AIAgent()
    a._rate_limiter = RateLimiter(max_calls=2, window_s=60)
    return a


def test_agent_rate_limit_trips(agent):
    with mock.patch.object(agent, "_execute_tool",
                           return_value="ok"):
        agent._dispatch_tool_call("web_search", {"query": "a"})
        agent._dispatch_tool_call("web_search", {"query": "b"})
        assert agent.rate_limited is False
        resp = agent._dispatch_tool_call("web_search", {"query": "c"})
    assert agent.rate_limited is True
    assert "Rate limit exceeded" in resp
    # policy engine DENYs non-READ while the flag is set
    from access_os.policy import PolicyContext, decide_tool_call, Decision
    ctx = PolicyContext(rate_limited=agent.rate_limited)
    d, _ = decide_tool_call("open_application", {"app_name": "x"}, ctx,
                            level=3)
    assert d == Decision.DENY


def test_agent_breaker_open_pauses_tools(agent):
    for _ in range(5):
        agent._breaker.record_failure()
    resp = agent._dispatch_tool_call("web_search", {"query": "x"})
    assert "temporarily paused" in resp


def test_agent_breaker_counts_crashes(agent):
    agent._rate_limiter = RateLimiter(max_calls=100, window_s=60)
    with mock.patch.object(agent, "_execute_tool",
                           side_effect=RuntimeError("boom")):
        for _ in range(5):
            agent._dispatch_tool_call("web_search", {"query": "x"})
    assert agent._breaker.state == "open"
