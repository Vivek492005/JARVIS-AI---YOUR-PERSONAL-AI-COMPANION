"""
JARVIS - AI Voice Companion (GUI Mode)
Launches the floating JARVIS companion widget.
"""

import os
import sys
import queue
import signal
import logging
import threading
from logging.handlers import RotatingFileHandler

from access_os.voice_interface import VoiceInterface, VoiceCommand
from access_os.first_run import ensure_api_keys
from gui import JARVISGUI

# ── Logging ──────────────────────────────────────────────────────────────────
# F-15: rotating logs (was unbounded FileHandler) + signal import actually used.
def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            RotatingFileHandler("jarvis.log", maxBytes=5_000_000, backupCount=3,
                                encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


_setup_logging()
logger = logging.getLogger("JARVIS")


class JARVISAssistant:
    """Orchestrates the JARVIS voice backend and the GUI companion."""

    def __init__(self):
        self.running = False
        self.gui: JARVISGUI | None = None
        # F-11: single command queue — one action at a time, never parallel
        # pyautogui streams from two threads.
        self._cmd_q: "queue.Queue[str | None]" = queue.Queue()

        logger.info("Initializing JARVIS Voice Companion…")
        self.voice = VoiceInterface(
            config_file="voice_config.json",
            status_callback=self._on_ai_status
        )

        # Hook into voice.speak() so every TTS output is also shown in the GUI
        self._orig_speak = self.voice.speak
        self.voice.speak = self._hooked_speak

    def _on_ai_status(self, status: str):
        """Update GUI with current AI agent status (thinking, tool execution, etc)."""
        if self.gui is not None:
            self.gui.set_status(f"⚡ {status}")

    # ── TTS hook ──────────────────────────────────────────────────────────────

    def _hooked_speak(self, text: str, wait: bool = False):
        """Forward every spoken line to the GUI status label (thread-safe)."""
        if self.gui is not None:
            self.gui.set_assistant_text(str(text))
        self._orig_speak(text, wait)

    # ── Voice command callback ─────────────────────────────────────────────────

    def on_voice_command(self, cmd: VoiceCommand):
        """Called by VoiceInterface when a command is recognised."""
        if self.gui is not None:
            self.gui.set_user_text(cmd.text)
            # F-13: this is the thinking state, not "Listening...".
            self.gui.set_status("⚡ Thinking...")

    def send_text_command(self, text: str):
        """Enqueue a typed command; the _cmd_loop worker runs it serially."""
        if not text.strip():
            return
        if self.gui is not None:
            self.gui.set_user_text(text)
        self._cmd_q.put(text)

    def _cmd_loop(self):
        """Single worker: one command at a time, status always restored."""
        while self.running:
            text = self._cmd_q.get()
            if text is None:  # shutdown sentinel from stop()
                break
            try:
                if self.gui is not None:
                    self.gui.set_status("⚡ Thinking...")
                # F-12: no unused `resp`; exceptions must not wedge the status.
                self.voice.execute_text_command(text)
            except Exception:
                logger.exception("command failed: %r", text)
            finally:
                # F-12: status returns to Ready even when the command raised.
                if self.gui is not None:
                    self.gui.set_status("● Ready")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        """Create the companion GUI and start voice listening."""
        self.running = True

        # F-11: start the single command worker before anything can enqueue.
        threading.Thread(target=self._cmd_loop, daemon=True,
                         name="JARVIS-cmd-loop").start()

        # Build companion widget
        self.gui = JARVISGUI(self)

        # Start mic listening in background
        self.voice.start_listening(callback=self.on_voice_command)

        # Initial welcome greeting slightly after start
        self.gui.root.after(600, lambda: self.voice.speak(
            "JARVIS is online and ready for your commands.", wait=False
        ))

        # Enter GUI event loop (blocks main thread until window closed)
        self.gui.show()

    def stop(self):
        """Clean shutdown — safe to call from any thread."""
        if not self.running:
            return
        self.running = False
        # Unblock the _cmd_loop worker if it is waiting on the queue.
        self._cmd_q.put(None)
        logger.info("JARVIS shutting down…")
        try:
            self.voice.stop_listening()
        except Exception as e:
            logger.error(f"Error stopping listener: {e}")
        logger.info("JARVIS shutdown complete.")


# ── Entry point ───────────────────────────────────────────────────────────────

def _self_test() -> int:
    """Smoke test for the packaged build (CI runs `JARVIS.exe --self-test`).

    No GUI, no network, no microphone: just proves the security gate and the
    unified action executors are intact inside the bundle.
    """
    from access_os.command_policy import check_tool_call
    from access_os.actions import run_action

    assert check_tool_call(
        "run_powershell_command", {"command": "Remove-Item x"})[0] == "deny"
    assert check_tool_call(
        "run_powershell_command", {"command": "Get-Date"})[0] == "allow"
    assert check_tool_call(
        "keyboard_mouse_action",
        {"action": "press_hotkey", "value": "alt+f4"})[0] == "deny"

    verdict, result = run_action(
        "manage_notes", {"action": "save", "content": "self-test"})
    assert verdict == "allow", result
    assert os.path.exists("notes.txt")
    os.remove("notes.txt")

    print("JARVIS self-test OK")
    return 0


def main():
    if "--self-test" in sys.argv:
        sys.exit(_self_test())

    # Change working directory to project root so relative paths work
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    # First-run API key dialog for non-technical users (silent no-op if keys
    # are already configured). Never blocks startup.
    ensure_api_keys()

    assistant = JARVISAssistant()

    # F-15: graceful shutdown on Ctrl+C / taskkill — was an unused import.
    def _handle_signal(signum, frame):
        logger.info(f"Received signal {signum}; shutting down…")
        assistant.stop()

    for _sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(_sig, _handle_signal)
        except (OSError, ValueError) as e:
            logger.warning(f"Could not install handler for {_sig}: {e}")

    # Task 1.9: scrub secret values out of every log record from here on.
    try:
        from access_os.secrets import install_secret_redaction
        install_secret_redaction()
    except Exception as e:
        logger.warning(f"Secret log-redaction unavailable: {e}")

    # Task 1.8: kill switch — Ctrl+Alt+Shift+J stops everything, now.
    try:
        from access_os.safety import KillSwitch
        _kill = KillSwitch()
        _kill.on_trigger(lambda: assistant.stop())
        _kill.install_hotkey()  # best-effort; False on Linux / no package
    except Exception as e:
        logger.warning(f"Kill switch unavailable: {e}")

    assistant.start()


if __name__ == "__main__":
    main()
