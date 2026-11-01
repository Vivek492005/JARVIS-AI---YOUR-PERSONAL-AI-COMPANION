"""Tests for the voice interface module."""

import sys
import unittest
from unittest.mock import MagicMock, patch

# Stub display/Windows-only modules so tests run headless on any OS.
# (speech_recognition / pyttsx3 are real test dependencies.)
for _mod in ("pyautogui",):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))

from access_os.voice_interface import VoiceInterface, VoiceCommand


class TestVoiceInterface(unittest.TestCase):
    """Test cases for the VoiceInterface class."""

    def setUp(self):
        """Set up test fixtures."""
        self.voice_interface = VoiceInterface()
        self.voice_interface.wake_word = "test"
        self.voice_interface.engine = MagicMock()
        self.voice_interface.recognizer = MagicMock()
        self.voice_interface.microphone = MagicMock()

    def test_speak(self):
        """Test the speak method."""
        test_text = "Hello, world!"
        # wait=True -> synchronous, so the mocked engine assertions are deterministic
        self.voice_interface.speak(test_text, wait=True)
        self.voice_interface.engine.say.assert_called_once_with(test_text)
        self.voice_interface.engine.runAndWait.assert_called_once()

    @patch('access_os.voice_interface.threading.Thread')
    def test_speak_async(self, mock_thread):
        """Test the speak method with async=True."""
        test_text = "Hello, async world!"
        self.voice_interface.speak(test_text, wait=False)
        mock_thread.assert_called_once()

    def test_stop_listening(self):
        """Test the stop_listening method."""
        self.voice_interface.is_listening = True
        thread = MagicMock()
        thread.is_alive.return_value = True
        self.voice_interface._listen_thread = thread

        self.voice_interface.stop_listening()
        self.assertFalse(self.voice_interface.is_listening)
        thread.join.assert_called_once_with(timeout=4.0)
        self.assertIsNone(self.voice_interface._listen_thread)


class TestVoiceCommand(unittest.TestCase):
    """Test cases for the VoiceCommand dataclass."""

    def test_voice_command_creation(self):
        """Test creation of VoiceCommand objects."""
        cmd = VoiceCommand("test command", 0.95, True)
        self.assertEqual(cmd.text, "test command")
        self.assertEqual(cmd.confidence, 0.95)
        self.assertTrue(cmd.is_final)


if __name__ == "__main__":
    unittest.main()
