"""Tests for Phase 5.3 screen capture + OCR + privacy filter."""

import sys
import time

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, "tests")

from jarvis.perception import screen as screen_mod  # noqa: E402
from jarvis.perception.privacy import SensitiveWindowError  # noqa: E402
from jarvis.perception.screen import (  # noqa: E402
    ScreenCapture,
    _prune_shots,
    get_shot,
)
from jarvis.tools.registry import REGISTRY, Risk  # noqa: E402
from fakes.fake_desktop import install_fake_desktop, uninstall_fake_desktop  # noqa: E402


@pytest.fixture()
def desktop():
    made = install_fake_desktop()
    uia = made["uia"]
    uia.add_window("Untitled - Notepad", "notepad.exe")
    uia.add_window("KeePassXC", "keepassxc.exe")
    yield made
    uninstall_fake_desktop()
    screen_mod._SHOTS.clear()


def test_capture_active_window_to_memory(desktop):
    cap = ScreenCapture()
    info = cap.capture()
    assert info["window"] == "Untitled - Notepad"
    assert info["shot_id"].startswith("shot-")
    assert info["bytes"] > 0
    assert info["on_disk"] is None
    assert get_shot(info["shot_id"]) is not None


def test_capture_refuses_sensitive_window(desktop):
    made = desktop
    sens = [h for h, w in made["uia"].windows.items() if "keepass" in w.title.lower()][0]
    cap = ScreenCapture()
    with pytest.raises(SensitiveWindowError):
        cap.capture(handle=sens)


def test_read_screen_text_redacts(desktop):
    made = desktop
    made["ocr"].text = "card 4111 1111 1111 1111 ok"
    cap = ScreenCapture()
    out = cap.read_text()
    assert "4111" not in out
    assert "[REDACTED]" in out


def test_read_screen_text_refuses_sensitive(desktop):
    made = desktop
    sens = [h for h, w in made["uia"].windows.items() if "keepass" in w.title.lower()][0]
    cap = ScreenCapture()
    with pytest.raises(SensitiveWindowError):
        cap.read_text(handle=sens)


def test_shot_cache_bounded(desktop):
    cap = ScreenCapture()
    for _ in range(25):
        cap.capture()
    assert len(screen_mod._SHOTS) <= 20


def test_prune_old_screenshots(tmp_path):
    old = tmp_path / "shot-0001.png"
    old.write_bytes(b"x")
    ancient = time.time() - 30 * 3600
    import os

    os.utime(old, (ancient, ancient))
    new = tmp_path / "shot-0002.png"
    new.write_bytes(b"y")
    removed = _prune_shots(tmp_path, max_age_s=24 * 3600)
    assert removed == 1
    assert not old.exists() and new.exists()


def test_tools_registered():
    assert REGISTRY["capture_screen"].risk == Risk.READ
    assert REGISTRY["read_screen_text"].risk == Risk.READ
    assert REGISTRY["read_screen_text"].carries_external_data is True


def test_run_action_capture_and_read(desktop):
    from jarvis.tools.actions import run_action

    verdict, result = run_action("capture_screen", {})
    assert verdict == "allow", result
    assert "shot-" in result
    verdict, result = run_action("read_screen_text", {})
    assert verdict == "allow", result
