"""Tests for perception privacy blocklist (5.2/5.3 foundation)."""

import sys

sys.path.insert(0, "src")
from jarvis.perception.privacy import (
    SensitiveWindowError,
    check_window,
    is_sensitive_window,
    redact_text,
)


def test_password_manager_blocked():
    assert is_sensitive_window("KeePassXC", "keepassxc.exe")
    assert is_sensitive_window("1Password", "1password.exe")
    assert is_sensitive_window("Bitwarden Vault", "chrome.exe")


def test_banking_blocked():
    assert is_sensitive_window("HDFC NetBanking", "msedge.exe")
    assert is_sensitive_window("Zerodha Kite", "chrome.exe")


def test_incognito_blocked():
    assert is_sensitive_window("New Incognito Tab", "chrome.exe")


def test_normal_window_allowed():
    assert not is_sensitive_window("Untitled - Notepad", "notepad.exe")
    assert not is_sensitive_window("VS Code", "code.exe")


def test_check_window_raises():
    try:
        check_window("KeePass", "keepass.exe")
        raise AssertionError("should have raised")
    except SensitiveWindowError:
        pass


def test_redact_text_cards_and_passwords():
    out = redact_text("card 4111 1111 1111 1111 and password=hunter2 ok")
    assert "4111" not in out and "[REDACTED]" in out
    assert "hunter2" not in out
