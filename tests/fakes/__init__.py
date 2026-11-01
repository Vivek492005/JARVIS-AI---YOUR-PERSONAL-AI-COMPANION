"""Test fakes for the JARVIS test architecture (Master Plan Task 2.8).

No mic, no network, no OS side effects — the whole voice → tool →
reply flow runs in CI on these.
"""

from tests.fakes.fake_llm import FakeLLM
from tests.fakes.fake_mic import FakeMic
from tests.fakes.fake_os import FakeOS
from tests.fakes.fake_stt import FakeSTT

__all__ = ["FakeLLM", "FakeMic", "FakeOS", "FakeSTT"]
