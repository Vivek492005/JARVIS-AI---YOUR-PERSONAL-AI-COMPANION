"""Tests for Task 0.8: main.py command queue, status recovery, signal wiring."""

import sys
import time
from unittest.mock import MagicMock, patch

# Stub display-only modules so `import main` works headless.
for _mod in ("pyautogui",):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))

import main as main_mod  # noqa: E402
from main import JARVISAssistant  # noqa: E402


def _assistant():
    """JARVISAssistant with VoiceInterface/GUI mocked out."""
    with patch.object(main_mod, "VoiceInterface"), patch.object(main_mod, "JARVISGUI"):
        a = JARVISAssistant()
    a.voice = MagicMock()
    a.gui = MagicMock()
    return a


def test_send_text_command_enqueues():
    a = _assistant()
    a.send_text_command("hello")
    assert a._lanes.qsize() == 1


def test_send_text_command_ignores_blank():
    a = _assistant()
    a.send_text_command("   ")
    assert a._lanes.qsize() == 0


def test_lane_serial_and_status_restored():
    """Task 2.3: the lane runs commands serially with status recovery."""
    a = _assistant()
    seen = []
    a.voice.execute_text_command.side_effect = lambda t: seen.append(t)
    a._lanes.start()
    try:
        a.send_text_command("one")
        a.send_text_command("two")
        deadline = time.time() + 5
        while len(seen) < 2 and time.time() < deadline:
            time.sleep(0.01)
        assert seen == ["one", "two"]  # serial, in order
        # status went Thinking... then back to Ready for each command
        statuses = [c.args[0] for c in a.gui.set_status.call_args_list]
        assert statuses.count("⚡ Thinking...") == 2
        assert statuses.count("● Ready") == 2
    finally:
        a._lanes.stop()


def test_lane_exception_still_restores_ready():
    a = _assistant()
    a.voice.execute_text_command.side_effect = RuntimeError("boom")
    a._lanes.start()
    try:
        a.send_text_command("bad command")
        deadline = time.time() + 5
        while a._lanes.qsize() > 0 and time.time() < deadline:
            time.sleep(0.01)
        time.sleep(0.2)
        statuses = [c.args[0] for c in a.gui.set_status.call_args_list]
        assert "● Ready" in statuses  # F-12: never wedged on "Processing…"
    finally:
        a._lanes.stop()


def test_on_voice_command_status_is_thinking():
    a = _assistant()
    cmd = MagicMock()
    cmd.text = "hello jarvis"
    a.on_voice_command(cmd)
    a.gui.set_status.assert_called_with("⚡ Thinking...")  # F-13, not "Listening..."


def test_stop_stops_lane():
    a = _assistant()
    a.running = True
    a._lanes.start()
    a.stop()
    assert not a._lanes.running
    assert a.running is False


def test_logging_uses_rotating_handler():
    import logging
    import logging.handlers

    root = logging.getLogger()
    old = root.handlers[:]
    root.handlers.clear()
    try:
        main_mod._setup_logging()
        assert any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers)
    finally:
        root.handlers.clear()
        root.handlers.extend(old)
