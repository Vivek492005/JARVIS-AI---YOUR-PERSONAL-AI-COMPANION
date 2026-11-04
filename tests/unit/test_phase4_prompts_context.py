"""Tests for Phase 4.3 (prompt architecture) and 4.5 (context management)."""

import sys
from unittest.mock import MagicMock

sys.modules.setdefault("pyautogui", MagicMock(name="pyautogui"))

from jarvis.brain.context import (  # noqa: E402
    ContextManager,
    LastEntities,
    estimate_tokens,
    truncate_tool_output,
)
from jarvis.brain.prompts import PROMPT_VERSION, PromptBuilder  # noqa: E402


class TestPromptBuilder:
    def test_all_six_layers_present(self):
        pb = PromptBuilder()
        sp = pb.build(memory_facts=["default browser: Chrome"], live_extra={"mode": "test"})
        assert "JARVIS" in sp  # identity
        assert "Chrome" in sp  # user profile / memory facts
        assert "Untrusted data" in sp or "untrusted_data" in sp  # safety
        assert "open_application" in sp  # tool catalog
        assert "mode: test" in sp  # live context
        assert "Hinglish" in sp  # style
        assert PROMPT_VERSION in sp

    def test_tool_catalog_lists_all_tools(self):
        from jarvis.brain.prompts.builder import tool_catalog
        from jarvis.tools.registry import REGISTRY

        cat = tool_catalog()
        for name in REGISTRY:
            if "." not in name:
                assert name in cat

    def test_version_bump_format(self):
        assert PROMPT_VERSION.count(".") == 2


class TestContextManager:
    def test_rolling_window_and_summarization(self):
        cm = ContextManager(max_turns=6, token_budget=10_000_000)
        for i in range(10):
            cm.add_turn("user", f"question {i}")
        assert len(cm.turns) <= 6
        assert len(cm.summaries) >= 1
        assert cm.summaries[0].turns_covered >= 1

    def test_token_budget_triggers_summary(self):
        cm = ContextManager(max_turns=1000, token_budget=50)
        for _ in range(10):
            cm.add_turn("user", "x" * 100)
        assert len(cm.summaries) >= 1

    def test_build_messages_shape(self):
        cm = ContextManager()
        cm.add_turn("user", "hello")
        cm.add_turn("assistant", "hi")
        msgs = cm.build_messages("SYS")
        assert msgs[0] == {"role": "system", "content": "SYS"}
        assert msgs[1]["role"] == "user"

    def test_truncate_tool_output(self):
        long = "x" * 5000
        short = truncate_tool_output(long, max_chars=1000)
        assert len(short) < 1100 and "truncated" in short
        assert truncate_tool_output("abc") == "abc"

    def test_estimate_tokens(self):
        assert estimate_tokens("abcd") == 1
        assert estimate_tokens("a" * 400) == 100


class TestLastEntities:
    def test_record_and_resolve(self):
        le = LastEntities()
        le.record("file", "report.pdf")
        assert le.resolve_reference("wo wala file") == "report.pdf"
        assert le.resolve_reference("khol do") is None

    def test_priority_fallback(self):
        le = LastEntities()
        le.record("app", "chrome")
        assert le.resolve_reference("wo") == "chrome"
