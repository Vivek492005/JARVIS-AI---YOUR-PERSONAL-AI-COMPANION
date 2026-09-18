"""
Voice Interface Module for ACCESS-OS
Handles speech recognition and text-to-speech functionality.
"""

import queue
import threading
import logging
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any

import speech_recognition as sr
import pyttsx3


@dataclass
class VoiceCommand:
    """Represents a recognized voice command."""
    text: str
    confidence: float
    is_final: bool = True


class VoiceInterface:
    """Handles voice input and output for ACCESS-OS."""

    def __init__(self, wake_word: str = "access"):
        """Initialize the voice interface.
        
        Args:
            wake_word: The word that activates the voice interface
        """
        self.wake_word = wake_word.lower()
        self.recognizer = sr.Recognizer()
        self.engine = pyttsx3.init()
        self.command_queue = queue.Queue()
        self.is_listening = False
        self.listening_thread = None
        self.callback = None
        self.logger = logging.getLogger(__name__)

    def speak(self, text: str) -> None:
        """Convert text to speech.
        
        Args:
            text: The text to speak
        """
        self.engine.say(text)
        self.engine.runAndWait()

    def listen(self) -> Optional[str]:
        """Listen for speech input and return the recognized text.
        
        Returns:
            The recognized text, or None if no speech was detected
        """
        with sr.Microphone() as source:
            self.logger.info("Listening...")
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                text = self.recognizer.recognize_google(audio).lower()
                self.logger.debug(f"Recognized: {text}")
                return text
            except sr.WaitTimeoutError:
                self.logger.debug("No speech detected")
                return None
            except sr.UnknownValueError:
                self.logger.debug("Could not understand audio")
                return None
            except Exception as e:
                self.logger.error(f"Error in speech recognition: {e}")
                return None

    def _listen_loop(self) -> None:
        """Continuously listen for voice commands and add them to the queue."""
        while self.is_listening:
            text = self.listen()
            if text and text.startswith(self.wake_word):
                command = text[len(self.wake_word):].strip()
                if command:
                    cmd = VoiceCommand(text=command, confidence=1.0)
                    self.command_queue.put(cmd)
                    if self.callback:
                        self.callback(cmd)

    def start_listening(self, callback: Optional[Callable[[VoiceCommand], None]] = None) -> None:
        """Start the voice interface.
        
        Args:
            callback: Optional function to call when a command is received
        """
        if self.is_listening:
            return
            
        self.callback = callback
        self.is_listening = True
        self.listening_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listening_thread.start()
        self.logger.info("Voice interface started")

    def stop_listening(self) -> None:
        """Stop the voice interface."""
        self.is_listening = False
        if self.listening_thread:
            self.listening_thread.join(timeout=1)
            self.listening_thread = None
        self.logger.info("Voice interface stopped")

    def get_command(self, timeout: Optional[float] = None) -> Optional[VoiceCommand]:
        """Get the next voice command from the queue.
        
        Args:
            timeout: Maximum time to wait for a command, in seconds
            
        Returns:
            The next VoiceCommand, or None if the queue is empty
        """
        try:
            return self.command_queue.get(timeout=timeout)
        except queue.Empty:
            return None
            
    def __del__(self):
        """Cleanup resources."""
        self.stop_listening()
        if hasattr(self, 'engine'):
            self.engine.stop()


if __name__ == "__main__":
    # Example usage
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    def command_handler(cmd: VoiceCommand):
        print(f"Command received: {cmd.text}")
    
    vi = VoiceInterface()
    print("Say 'access' followed by your command...")
    vi.start_listening(command_handler)
    
    try:
        while True:
            cmd = vi.get_command(timeout=1)
            if cmd:
                print(f"Processed command: {cmd.text}")
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        vi.stop_listening()
