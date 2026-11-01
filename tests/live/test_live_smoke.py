"""Live provider smoke tests — OPT-IN ONLY (see README.md).

Real network, real APIs, real keys. Never runs in CI.
"""

import os

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.getenv("JARVIS_LIVE_TESTS"), reason="opt-in: set JARVIS_LIVE_TESTS=1"
    ),
]


def test_live_provider_health():
    """Every configured provider answers a cheap health ping."""
    from jarvis.brain.providers import DeepSeek, HuggingFaceRouter
    from jarvis.core.secrets import get_secret

    checked = 0
    if get_secret("HUGGINGFACE_API_KEY"):
        assert HuggingFaceRouter(api_key=get_secret("HUGGINGFACE_API_KEY")).health()
        checked += 1
    if get_secret("DEEPSEEK_API_KEY"):
        assert DeepSeek(api_key=get_secret("DEEPSEEK_API_KEY")).health()
        checked += 1
    if not checked:
        pytest.skip("no provider API keys configured")


def test_live_chat_roundtrip():
    """One real chat round-trip through the chain (costs a few cents)."""
    from jarvis.brain.agent import AIAgent

    agent = AIAgent()
    if not agent.chain.provider_names:
        pytest.skip("no cloud providers configured")
    reply = agent.process("Say exactly: live test ok")
    assert isinstance(reply, str) and reply
