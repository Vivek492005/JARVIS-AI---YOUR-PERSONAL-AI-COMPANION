"""Tests for Phase 5.1 control-surface ladder."""

import sys

import pytest

sys.path.insert(0, "src")

from jarvis.perception.ladder import (  # noqa: E402
    Attempt,
    AttemptFailed,
    LadderExhausted,
    Rung,
    RUNG_LABELS,
    run_ladder,
    rung_for_tool,
)


def test_highest_rung_wins():
    attempts = [
        Attempt(Rung.VLM, "vlm", lambda: "vlm-result"),
        Attempt(Rung.UIA, "uia", lambda: "uia-result"),
        Attempt(Rung.API_MCP, "api", lambda: "api-result"),
    ]
    rung, result = run_ladder("do thing", attempts, audit=False)
    assert rung == Rung.API_MCP
    assert result == "api-result"


def test_fallback_to_next_rung_on_attempt_failed():
    seen = []

    def fail():
        seen.append("uia")
        raise AttemptFailed("button not found")

    attempts = [
        Attempt(Rung.UIA, "uia", fail),
        Attempt(Rung.OCR, "ocr", lambda: "ocr-result"),
    ]
    rung, result = run_ladder("click x", attempts, audit=False)
    assert rung == Rung.OCR
    assert result == "ocr-result"
    assert seen == ["uia"]


def test_unavailable_rungs_skipped_silently():
    attempts = [
        Attempt(Rung.UIA, "uia", lambda: "uia", available=False),
        Attempt(Rung.DOM, "dom", lambda: "dom-result"),
    ]
    rung, result = run_ladder("t", attempts, audit=False)
    assert rung == Rung.DOM


def test_ladder_exhausted_carries_reasons():
    attempts = [
        Attempt(Rung.UIA, "uia", lambda: (_ for _ in ()).throw(AttemptFailed("nope"))),
        Attempt(Rung.OCR, "ocr", lambda: (_ for _ in ()).throw(AttemptFailed("blind"))),
    ]
    with pytest.raises(LadderExhausted) as exc:
        run_ladder("t", attempts, audit=False)
    assert len(exc.value.failures) == 2
    assert "nope" in str(exc.value)


def test_unexpected_exception_also_falls_through():
    def boom():
        raise RuntimeError("kaboom")

    attempts = [
        Attempt(Rung.UIA, "uia", boom),
        Attempt(Rung.DOM, "dom", lambda: "dom-ok"),
    ]
    rung, result = run_ladder("t", attempts, audit=False)
    assert rung == Rung.DOM
    assert result == "dom-ok"


def test_fallback_is_audit_logged(tmp_path, monkeypatch):
    import jarvis.policy.audit as audit_mod

    logged = []

    class FakeLogger:
        def log(self, tool, args, decision, reason="", latency_ms=None):
            logged.append((tool, args, decision, reason))

    monkeypatch.setattr(audit_mod, "AuditLogger", lambda *a, **k: FakeLogger())

    def fail():
        raise AttemptFailed("UIA miss")

    run_ladder(
        "click save",
        [
            Attempt(Rung.UIA, "uia", fail),
            Attempt(Rung.OCR, "ocr", lambda: "ok"),
        ],
        audit=True,
    )

    assert len(logged) == 1
    tool, args, decision, reason = logged[0]
    assert tool == "ladder.fallback"
    assert decision == "fallback"
    assert args["from"] == RUNG_LABELS[Rung.UIA]
    assert args["to"] == RUNG_LABELS[Rung.OCR]
    assert "UIA miss" in reason


def test_rung_labels_complete():
    assert set(RUNG_LABELS) == set(Rung)


def test_rung_for_tool_known():
    assert rung_for_tool("browser_click") == Rung.DOM
    assert rung_for_tool("vlm_click") == Rung.VLM
    assert rung_for_tool("read_screen_text") == Rung.OCR
