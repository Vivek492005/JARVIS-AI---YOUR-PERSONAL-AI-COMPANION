"""Tests for Task 1.9: secrets handling.

Keyring priority/degradation, log redaction filter, no hardcoded secrets.
"""

import logging
import os
import sys
from unittest import mock

import pytest

from access_os import secrets as S


# ---------------------------------------------------------------------------
# get_secret priority: env > keyring > ""
# ---------------------------------------------------------------------------

class _FakeKR:
    _v = "kr-key"

    @staticmethod
    def get_password(svc, acct):
        return _FakeKR._v

    @staticmethod
    def set_password(svc, acct, val):
        _FakeKR._v = val

    @staticmethod
    def delete_password(svc, acct):
        _FakeKR._v = None


def test_env_wins_over_keyring(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "env-key")
    with mock.patch.object(S, "keyring_available", return_value=True), \
         mock.patch.dict(sys.modules, {"keyring": _FakeKR}):
        assert S.get_secret("HUGGINGFACE_API_KEY") == "env-key"


def test_keyring_fallback(monkeypatch):
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    with mock.patch.object(S, "keyring_available", return_value=True), \
         mock.patch.dict(sys.modules, {"keyring": _FakeKR}):
        assert S.get_secret("HUGGINGFACE_API_KEY") == "kr-key"


def test_graceful_without_keyring(monkeypatch):
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    with mock.patch.object(S, "keyring_available", return_value=False):
        assert S.get_secret("HUGGINGFACE_API_KEY") == ""
        assert S.store_secret("HUGGINGFACE_API_KEY", "x") is False


def test_store_roundtrip_with_fake_keyring(monkeypatch):
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    vault = {}

    class FakeKR:
        @staticmethod
        def get_password(svc, acct):
            return vault.get((svc, acct))

        @staticmethod
        def set_password(svc, acct, val):
            vault[(svc, acct)] = val

        @staticmethod
        def delete_password(svc, acct):
            vault.pop((svc, acct), None)

    with mock.patch.object(S, "keyring_available", return_value=True), \
         mock.patch.dict(sys.modules, {"keyring": FakeKR}):
        assert S.store_secret("HUGGINGFACE_API_KEY", "k1") is True
        assert S.get_secret("HUGGINGFACE_API_KEY") == "k1"
        assert S.delete_secret("HUGGINGFACE_API_KEY") is True
        assert S.get_secret("HUGGINGFACE_API_KEY") == ""


def test_status_never_includes_values(monkeypatch, capsys):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "super-secret-value")
    assert S.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "super-secret-value" not in out
    assert "HUGGINGFACE_API_KEY: env" in out


# ---------------------------------------------------------------------------
# Log redaction filter
# ---------------------------------------------------------------------------

def test_redacting_filter_scrubs_values():
    f = S.SecretRedactingFilter()
    f.add_secret("sk-live-12345678")
    f.add_secret("short")  # <8 chars: ignored
    rec = logging.LogRecord("t", logging.INFO, __file__, 1,
                            "calling with sk-live-12345678 now", (), None)
    assert f.filter(rec) is True
    assert "sk-live-12345678" not in rec.getMessage()
    assert "***REDACTED***" in rec.getMessage()


def test_redacting_filter_short_values_ignored():
    f = S.SecretRedactingFilter()
    f.add_secret("abc")
    assert f._values == []


def test_install_is_idempotent(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "env-key-12345678")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("RUMIK_API_KEY", raising=False)
    with mock.patch.object(S, "keyring_available", return_value=False):
        f1 = S.install_secret_redaction()
        f2 = S.install_secret_redaction()
        assert f1 is f2
        assert "env-key-12345678" in f1._values
    S._redacting_filter = None  # don't leak into other tests
    logging.getLogger().filters = [
        fl for fl in logging.getLogger().filters if fl is not f1]


# ---------------------------------------------------------------------------
# No hardcoded secrets in first-party source
# ---------------------------------------------------------------------------

def test_no_hardcoded_secrets_in_source():
    import pathlib
    import re
    patterns = [r"rk_live_[A-Za-z0-9_\-]{8,}", r"sk-[A-Za-z0-9]{20,}",
                r"ghp_[A-Za-z0-9]{20,}", r"xox[bpas]-[A-Za-z0-9\-]{8,}"]
    bad = []
    for p in list(pathlib.Path("access_os").rglob("*.py")) + \
            [pathlib.Path("main.py"), pathlib.Path("gui.py")]:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(),
                                 start=1):
            for pat in patterns:
                if re.search(pat, line):
                    bad.append(f"{p}:{i}")
    assert not bad, f"hardcoded secrets: {bad}"
