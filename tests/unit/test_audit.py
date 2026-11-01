"""Tests for Task 1.7: audit log (closes A-09).

Redaction, entry schema, daily jsonl layout, 90-day retention, query/CLI.
"""

import datetime
import json
from unittest import mock

import pytest

from access_os.audit import (
    REDACTED,
    AuditLogger,
    main as audit_main,
    query,
    redact_args,
    stats,
)


@pytest.fixture()
def log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return AuditLogger()


# ---------------------------------------------------------------------------
# A-09: secret redaction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", [
    "password", "passwd", "api_key", "apikey", "token", "access_token",
    "client_secret", "auth_header", "credentials", "private_key",
    "PASSWORD", "ApiKey",
])
def test_sensitive_key_names_redacted(key):
    assert redact_args({key: "supersecret123"})[key] == REDACTED


def test_token_shaped_values_redacted():
    assert redact_args({"x": "sk-abcdefgh12345678"})["x"] == REDACTED
    assert redact_args({"x": "ghp_abcdefgh12345678"})["x"] == REDACTED
    assert redact_args({"x": "hf_abcdefgh12345678"})["x"] == REDACTED


def test_nested_and_list_values_redacted():
    out = redact_args({"cfg": {"password": "p", "host": "h"},
                       "items": [{"token": "t"}]})
    assert out["cfg"]["password"] == REDACTED
    assert out["cfg"]["host"] == "h"
    assert out["items"][0]["token"] == REDACTED


def test_innocent_values_untouched():
    out = redact_args({"query": "weather in Pune", "count": 3})
    assert out == {"query": "weather in Pune", "count": 3}


def test_redaction_in_written_entry(log, tmp_path):
    log.log("web_search", {"query": "x", "api_key": "sk-abcdefgh12345678"},
            "allow", reason="ok")
    day = datetime.date.today().isoformat()
    raw = (tmp_path / "audit" / f"{day}.jsonl").read_text(encoding="utf-8")
    assert "sk-abcdefgh12345678" not in raw
    assert REDACTED in raw


# ---------------------------------------------------------------------------
# Entry schema + layout
# ---------------------------------------------------------------------------

def test_entry_schema(log, tmp_path):
    log.log("open_website", {"url_or_name": "https://example.com"},
            "deny", reason="scheme blocked", latency_ms=1.25)
    day = datetime.date.today().isoformat()
    entries = [json.loads(line) for line in
               (tmp_path / "audit" / f"{day}.jsonl")
               .read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 1
    e = entries[0]
    assert set(e) == {"ts", "principal", "tool", "args", "decision",
                      "reason", "latency_ms", "session_id"}
    assert e["tool"] == "open_website"
    assert e["decision"] == "deny"
    assert e["principal"] == "user"
    assert e["latency_ms"] == 1.2  # rounded to 0.1
    assert len(e["session_id"]) == 12


def test_log_never_breaks_execution(tmp_path, monkeypatch):
    # Unwritable base -> log() swallows, caller unaffected.
    monkeypatch.chdir(tmp_path)
    bad = AuditLogger(base=tmp_path / "nope" / ".." / "audit")
    with mock.patch("pathlib.Path.mkdir", side_effect=OSError("disk full")):
        bad.log("x", {}, "allow")  # must not raise


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

def test_prune_deletes_old_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log = AuditLogger()
    old = datetime.date.today() - datetime.timedelta(days=91)
    new = datetime.date.today() - datetime.timedelta(days=10)
    (tmp_path / "audit").mkdir()
    (tmp_path / "audit" / f"{old.isoformat()}.jsonl").write_text("{}\n")
    (tmp_path / "audit" / f"{new.isoformat()}.jsonl").write_text("{}\n")
    removed = log.prune()
    assert removed == 1
    assert not (tmp_path / "audit" / f"{old.isoformat()}.jsonl").exists()
    assert (tmp_path / "audit" / f"{new.isoformat()}.jsonl").exists()


# ---------------------------------------------------------------------------
# Query + CLI
# ---------------------------------------------------------------------------

def test_query_filters(log):
    log.log("web_search", {"query": "a"}, "allow")
    log.log("open_website", {"url_or_name": "x"}, "deny")
    log.log("web_search", {"query": "b"}, "allow")
    assert len(query(tool="web_search")) == 2
    assert len(query(decision="deny")) == 1
    assert len(query(limit=1)) == 1
    s = stats()
    assert s["entries"] == 3
    assert s["by_tool"]["web_search"] == 2
    assert s["by_decision"]["deny"] == 1


def test_cli_tail_and_stats(log, capsys):
    log.log("web_search", {"query": "a"}, "allow", latency_ms=2.0)
    assert audit_main(["tail", "-n", "5"]) == 0
    out = capsys.readouterr().out
    assert "web_search" in out and "allow" in out
    assert audit_main(["stats"]) == 0
    assert "entries: 1" in capsys.readouterr().out


def test_cli_prune(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    old = datetime.date.today() - datetime.timedelta(days=100)
    (tmp_path / "audit").mkdir()
    (tmp_path / "audit" / f"{old.isoformat()}.jsonl").write_text("{}\n")
    assert audit_main(["prune"]) == 0
    assert "pruned 1" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# End to end through the agent
# ---------------------------------------------------------------------------

def test_agent_audit_uses_jsonl_with_decision(tmp_path, monkeypatch):
    import sys
    from unittest.mock import MagicMock
    for _mod in ("speech_recognition", "pyttsx3", "pyautogui", "pyperclip",
                 "fuzzywuzzy"):
        sys.modules.setdefault(_mod, MagicMock(name=_mod))
    sys.modules["fuzzywuzzy"].fuzz = MagicMock()
    monkeypatch.chdir(tmp_path)
    from access_os.ai_agent import AIAgent
    agent = AIAgent()
    with mock.patch.object(agent, "_execute_tool",
                           return_value="ok") as m:
        agent._dispatch_tool_call("web_search", {"query": "test"})
    m.assert_called_once()
    day = datetime.date.today().isoformat()
    entries = [json.loads(line) for line in
               (tmp_path / "audit" / f"{day}.jsonl")
               .read_text(encoding="utf-8").splitlines()]
    assert entries[-1]["decision"] == "allow"
    assert entries[-1]["session_id"] == agent.session_id
    assert entries[-1]["latency_ms"] is not None
