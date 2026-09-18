"""
JARVIS - AI Voice Companion (GUI Mode)
Launches the floating JARVIS companion widget.
"""

import os
import sys
import signal
import logging
import threading

from access_os.voice_interface import VoiceInterface, VoiceCommand
from gui import JARVISGUI

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("jarvis.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("JARVIS")


class JARVISAssistant:
    """Orchestrates the JARVIS voice backend and the GUI companion."""

    def __init__(self):
        self.running = False
        self.gui: JARVISGUI | None = None

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
            self.gui.set_status("● Listening...")

    def send_text_command(self, text: str):
        """Process typed command directly through the assistant pipeline."""
        if not text.strip():
            return
        if self.gui is not None:
            self.gui.set_user_text(text)
            self.gui.set_status("⚡ Processing...")

        def _worker():
            resp = self.voice.execute_text_command(text)
            if self.gui is not None:
                self.gui.set_status("● Ready")

        threading.Thread(target=_worker, daemon=True).start()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        """Create the companion GUI and start voice listening."""
        self.running = True

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
        logger.info("JARVIS shutting down…")
        try:
            self.voice.stop_listening()
        except Exception as e:
            logger.error(f"Error stopping listener: {e}")
        logger.info("JARVIS shutdown complete.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    # Change working directory to project root so relative paths work
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    assistant = JARVISAssistant()
    assistant.start()


if __name__ == "__main__":
    main()
