"""Tests for Task 2.5: provider abstraction + resilience."""

import random
from unittest import mock

import pytest

from jarvis.brain.providers import (Completion, DeepSeek,
                                    HuggingFaceRouter, LocalHeuristicProvider,
                                    Ollama, OpenAICompatibleProvider,
                                    ProviderChain, ToolCall)
from jarvis.core.errors import ProviderError, QuotaExhaustedError


class FakeLLM:
    """Scripted fake: each entry is a Completion or an Exception to raise."""

    def __init__(self, name, script):
        self._name = name
        self._script = list(script)
        self.attempts = 0

    @property
    def name(self):
        return self._name

    def complete(self, messages, tools=None, temperature=0.3):
        self.attempts += 1
        item = self._script.pop(0) if self._script else Completion(text="default")
        if isinstance(item, Exception):
            raise item
        item.provider = self._name
        return item

    def health(self):
        return True


def _chain(providers, **kw):
    kw.setdefault("sleep", lambda s: None)  # no real waiting in tests
    kw.setdefault("rng", random.Random(0))
    return ProviderChain(providers, **kw)


def test_chain_uses_first_healthy_provider():
    p1 = FakeLLM("p1", [Completion(text="from-p1")])
    p2 = FakeLLM("p2", [Completion(text="from-p2")])
    res = _chain([p1, p2]).complete([{"role": "user", "content": "hi"}])
    assert res.completion.text == "from-p1"
    assert res.provider_name == "p1"
    assert res.degraded is False
    assert p2.attempts == 0


def test_chain_retries_then_falls_back_with_honest_notice():
    notices = []
    p1 = FakeLLM("p1", [ProviderError("boom"), ProviderError("boom"),
                        ProviderError("boom")])
    p2 = FakeLLM("p2", [Completion(text="from-p2")])
    chain = _chain([p1, p2], on_degraded=notices.append)
    res = chain.complete([{"role": "user", "content": "hi"}])
    assert p1.attempts == 3  # initial + max 2 retries
    assert res.provider_name == "p2"
    assert res.degraded is True
    assert any("p1" in n and "switching provider" in n for n in notices)


def test_chain_quota_error_skips_retry():
    notices = []
    p1 = FakeLLM("p1", [QuotaExhaustedError("429")])
    p2 = FakeLLM("p2", [Completion(text="from-p2")])
    res = _chain([p1, p2], on_degraded=notices.append).complete(
        [{"role": "user", "content": "hi"}])
    assert p1.attempts == 1  # no retry on quota walls
    assert res.provider_name == "p2"
    assert any("quota exhausted" in n for n in notices)


def test_chain_backoff_is_exponential():
    sleeps = []
    p1 = FakeLLM("p1", [ProviderError("x")] * 3)
    p2 = FakeLLM("p2", [Completion(text="ok")])
    _chain([p1, p2], sleep=sleeps.append,
           rng=random.Random(0)).complete([{"role": "user", "content": "hi"}])
    assert len(sleeps) == 2
    # base 0.5 * 2^attempt + jitter[0, 0.25]
    assert 0.5 <= sleeps[0] <= 0.75
    assert 1.0 <= sleeps[1] <= 1.25


def test_circuit_breaker_opens_after_five_failures():
    p1 = FakeLLM("p1", [ProviderError("down")] * 100)
    p2 = FakeLLM("p2", [Completion(text="ok")] * 100)
    chain = _chain([p1, p2])
    msgs = [{"role": "user", "content": "hi"}]
    for _ in range(5):
        chain.complete(msgs)
    assert p1.attempts == 5 * 3  # 3 attempts per call (initial + 2 retries)
    # 6th call: breaker open → p1 skipped entirely
    before = p1.attempts
    res = chain.complete(msgs)
    assert p1.attempts == before
    assert res.provider_name == "p2"


def test_all_cloud_down_falls_to_local_heuristic_degraded():
    notices = []
    p1 = FakeLLM("p1", [ProviderError("down")] * 3)
    local = LocalHeuristicProvider(handler=lambda text: f"heuristic:{text}")
    res = _chain([p1], local_provider=local,
                 on_degraded=notices.append).complete(
        [{"role": "user", "content": "hello"}])
    assert res.provider_name == "local-heuristic"
    assert res.degraded is True
    assert res.completion.text == "heuristic:hello"
    assert any("local mode" in n for n in notices)


def test_no_providers_no_local_raises():
    with pytest.raises(ProviderError):
        _chain([]).complete([{"role": "user", "content": "hi"}])


def test_local_heuristic_uses_latest_user_message():
    local = LocalHeuristicProvider(handler=lambda t: f"got:{t}")
    comp = local.complete([
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "second"},
    ])
    assert comp.text == "got:second"
    assert comp.tool_calls == []
    assert local.health() is True


# -- OpenAI-compatible adapter --------------------------------------------

def _mock_openai_client(response=None, exc=None):
    client = mock.MagicMock()
    if exc is not None:
        client.chat.completions.create.side_effect = exc
    else:
        client.chat.completions.create.return_value = response
    return client


def _chat_response(text="hi", tool_calls=None):
    msg = mock.MagicMock()
    msg.content = text
    msg.tool_calls = tool_calls or []
    resp = mock.MagicMock()
    resp.choices = [mock.MagicMock(message=msg)]
    return resp


def test_adapter_normalizes_tool_calls():
    tc = mock.MagicMock()
    tc.id = "call_1"
    tc.function.name = "open_application"
    tc.function.arguments = '{"app_name": "notepad"}'
    client = _mock_openai_client(_chat_response("ok", [tc]))
    p = OpenAICompatibleProvider("test", "k", "http://x/v1", "m",
                                 client=client)
    comp = p.complete([{"role": "user", "content": "open notepad"}],
                      tools=[{"type": "function"}])
    assert comp.text == "ok"
    assert comp.tool_calls == [ToolCall(id="call_1", name="open_application",
                                        args={"app_name": "notepad"})]
    assert comp.provider == "test"
    _, kwargs = client.chat.completions.create.call_args
    assert kwargs["model"] == "m"
    assert kwargs["tool_choice"] == "auto"


def test_adapter_translates_429_to_quota_error():
    from openai import RateLimitError
    exc = RateLimitError("rate limited",
                         response=mock.MagicMock(status_code=429), body=None)
    client = _mock_openai_client(exc=exc)
    p = OpenAICompatibleProvider("test", "k", "http://x/v1", "m",
                                 client=client)
    with pytest.raises(QuotaExhaustedError):
        p.complete([{"role": "user", "content": "hi"}])


def test_adapter_wraps_generic_errors():
    client = _mock_openai_client(exc=ConnectionError("dns"))
    p = OpenAICompatibleProvider("test", "k", "http://x/v1", "m",
                                 client=client)
    with pytest.raises(ProviderError):
        p.complete([{"role": "user", "content": "hi"}])


def test_named_adapters_bind_env(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_MODEL", "Qwen/test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-test")
    monkeypatch.setenv("OLLAMA_MODEL", "tiny")
    hf = HuggingFaceRouter(api_key="k", client=mock.MagicMock())
    ds = DeepSeek(api_key="k", client=mock.MagicMock())
    ol = Ollama(client=mock.MagicMock())
    assert hf.name == "huggingface" and hf.model == "Qwen/test"
    assert ds.name == "deepseek" and ds.model == "deepseek-test"
    assert ol.name == "ollama" and ol.model == "tiny"


# -- agent wiring ----------------------------------------------------------

def test_agent_builds_chain_respecting_egress(monkeypatch):
    from jarvis.brain.agent import AIAgent
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "k1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k2")
    monkeypatch.setenv("PRIVACY__ALLOW_DEEPSEEK", "false")
    monkeypatch.setattr(AIAgent, "_ollama_wanted", staticmethod(lambda: False))
    from jarvis.core.config import reset_settings_cache
    reset_settings_cache()
    try:
        with mock.patch("openai.OpenAI", create=True):
            a = AIAgent.__new__(AIAgent)
            a.hf_api_key = "k1"
            a.ds_api_key = "k2"
            a.hf_base_url = "http://hf"
            a.ds_base_url = "http://ds"
            a.hf_model = "m1"
            a.ds_model = "m2"
            a.client = None          # __init__ sets these before _init_clients
            a.backup_client = None
            a._local_fallback_process = lambda text: "local"
            a._notify_status = lambda m: None
            AIAgent._init_clients(a)
        assert a.chain.provider_names == ["huggingface"]  # deepseek egress-denied
        assert a.client is not None and a.backup_client is None
    finally:
        reset_settings_cache()


def test_agent_process_uses_chain_tool_loop():
    """A tool call round-trip through the chain dispatches the tool."""
    from jarvis.brain.agent import AIAgent
    a = AIAgent.__new__(AIAgent)
    a.temperature = 0.3
    a.conversation_history = []
    a.max_history = 10
    a.tool_definitions = []
    a._get_system_prompt = lambda: "sys"
    a._dispatch_tool_call = lambda name, args: "tool-ok"
    a._sanitize_for_prompt = lambda n, al, r: r
    tc = ToolCall(id="c1", name="get_time", args={})
    a.chain = mock.MagicMock()
    a.chain.complete.side_effect = [
        mock.MagicMock(completion=Completion(text="", tool_calls=[tc],
                                             provider="fake")),
        mock.MagicMock(completion=Completion(text="done", tool_calls=[],
                                             provider="fake")),
    ]
    # _chain_complete unwraps .completion from chain.complete(...).
    a._chain_complete = lambda messages, tools=None: \
        a.chain.complete(messages, tools=tools).completion
    reply = AIAgent._call_llm_flow(a, "what time is it")
    assert reply == "done"
    assert a.chain.complete.call_count == 2
