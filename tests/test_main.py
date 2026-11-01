"""Tests for Task 0.8: main.py command queue, status recovery, signal wiring."""

import queue
import sys
import threading
import time
from unittest.mock import MagicMock, patch

# Stub display-only modules so `import main` works headless.
for _mod in ("pyautogui",):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))

import main as main_mod
from main import JARVISAssistant


def _assistant():
    """JARVISAssistant with VoiceInterface/GUI mocked out."""
    with patch.object(main_mod, "VoiceInterface") as vi, \
         patch.object(main_mod, "JARVISGUI"):
        a = JARVISAssistant()
    a.voice = MagicMock()
    a.gui = MagicMock()
    return a


def test_send_text_command_enqueues():
    a = _assistant()
    a.send_text_command("hello")
    assert a._cmd_q.get_nowait() == "hello"


def test_send_text_command_ignores_blank():
    a = _assistant()
    a.send_text_command("   ")
    assert a._cmd_q.empty()


def test_cmd_loop_serial_and_status_restored():
    a = _assistant()
    seen = []
    a.voice.execute_text_command.side_effect = lambda t: seen.append(t)
    a.running = True
    t = threading.Thread(target=a._cmd_loop, daemon=True)
    t.start()
    a.send_text_command("one")
    a.send_text_command("two")
    deadline = time.time() + 5
    while len(seen) < 2 and time.time() < deadline:
        time.sleep(0.01)
    a.running = False
    a._cmd_q.put(None)
    t.join(timeout=5)
    assert seen == ["one", "two"]  # serial, in order
    # status went Thinking... then back to Ready for each command
    statuses = [c.args[0] for c in a.gui.set_status.call_args_list]
    assert statuses.count("⚡ Thinking...") == 2
    assert statuses.count("● Ready") == 2


def test_cmd_loop_exception_still_restores_ready():
    a = _assistant()
    a.voice.execute_text_command.side_effect = RuntimeError("boom")
    a.running = True
    a._cmd_q.put("bad command")
    a._cmd_q.put(None)  # sentinel so the inline loop terminates
    a._cmd_loop()
    statuses = [c.args[0] for c in a.gui.set_status.call_args_list]
    assert "● Ready" in statuses  # F-12: never wedged on "Processing…"


def test_on_voice_command_status_is_thinking():
    a = _assistant()
    cmd = MagicMock()
    cmd.text = "hello jarvis"
    a.on_voice_command(cmd)
    a.gui.set_status.assert_called_with("⚡ Thinking...")  # F-13, not "Listening..."


def test_stop_unblocks_queue():
    a = _assistant()
    a.running = True
    t = threading.Thread(target=a._cmd_loop, daemon=True)
    t.start()
    a.stop()
    t.join(timeout=5)
    assert not t.is_alive()
    assert a.running is False


def test_logging_uses_rotating_handler():
    import logging
    import logging.handlers
    root = logging.getLogger()
    old = root.handlers[:]
    root.handlers.clear()
    try:
        main_mod._setup_logging()
        assert any(isinstance(h, logging.handlers.RotatingFileHandler)
                   for h in root.handlers)
    finally:
        root.handlers.clear()
        root.handlers.extend(old)
