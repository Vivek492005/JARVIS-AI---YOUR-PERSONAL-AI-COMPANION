"""
Fixed Voice Interface Module for ACCESS-OS
Handles speech recognition and text-to-speech functionality.
"""

import os
import json
import logging
import queue
import threading
import speech_recognition as sr
import pyttsx3

class VoiceInterface:
    def __init__(self, 
                 config_file: str = 'voice_config.json',
                 wake_word: str = "access",
                 energy_threshold: int = 300,
                 pause_threshold: float = 0.8,
                 phrase_time_limit: float = 5.0):
        """Initialize the voice interface with the given configuration."""
        self.logger = logging.getLogger(__name__)
        self.config_file = config_file
        
        # Initialize with default values
        self.voice_rate = 150
        self.voice_volume = 0.9
        self.voice_id = None
        self.language = 'en-US'
        self.continuous_listening = False
        self.auto_confirm = False
        self.wake_word = wake_word.lower()
        
        # Initialize recognizer
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = energy_threshold
        self.recognizer.pause_threshold = pause_threshold
        self.recognizer.phrase_time_limit = phrase_time_limit
        
        # Initialize TTS engine
        self.engine = None
        self._init_tts_engine()
        
        # Thread management
        self._stop_event = threading.Event()
        self._thread = None
        self.audio_queue = queue.Queue()
        
        # Load configuration
        self._load_config()
        
    def _load_config(self) -> None:
        """Load configuration from file or create default."""
        default_config = {
            'language': 'en-US',
            'voice_rate': 150,
            'voice_volume': 0.9,
            'voice_id': None,
            'wake_word': 'access',
            'energy_threshold': 300,
            'pause_threshold': 0.8,
            'phrase_time_limit': 5.0,
            'continuous_listening': False,
            'auto_confirm': False
        }
        
        # Try to load config file
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    default_config.update(config)
            except Exception as e:
                self.logger.error(f"Error loading config: {e}")
        else:
            # Create default config file
            self._save_config(default_config)
        
        # Apply configuration
        self.voice_rate = default_config.get('voice_rate', 150)
        self.voice_volume = default_config.get('voice_volume', 0.9)
        self.voice_id = default_config.get('voice_id')
        self.language = default_config.get('language', 'en-US')
        self.continuous_listening = default_config.get('continuous_listening', False)
        self.auto_confirm = default_config.get('auto_confirm', False)
        self.wake_word = default_config.get('wake_word', 'access').lower()
        self.recognizer.energy_threshold = default_config.get('energy_threshold', 300)
        self.recognizer.pause_threshold = default_config.get('pause_threshold', 0.8)
        self.recognizer.phrase_time_limit = default_config.get('phrase_time_limit', 5.0)
    
    def _save_config(self, config: dict) -> None:
        """Save configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
    
    def _init_tts_engine(self) -> None:
        """Initialize the text-to-speech engine."""
        try:
            self.engine = pyttsx3.init()
            voices = self.engine.getProperty('voices')
            if self.voice_id is not None and 0 <= self.voice_id < len(voices):
                self.engine.setProperty('voice', voices[self.voice_id].id)
            self.engine.setProperty('rate', self.voice_rate)
            self.engine.setProperty('volume', self.voice_volume)
        except Exception as e:
            self.logger.error(f"Failed to initialize TTS engine: {e}")
            self.engine = None
    
    def speak(self, text: str, wait: bool = True) -> None:
        """Convert text to speech."""
        if self.engine is None:
            self._init_tts_engine()
            if self.engine is None:
                self.logger.error("TTS engine not available")
                return
        
        try:
            self.engine.say(text)
            if wait:
                self.engine.runAndWait()
        except Exception as e:
            self.logger.error(f"Error in speech synthesis: {e}")
    
    def __del__(self):
        """Cleanup resources."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if hasattr(self, 'engine') and self.engine is not None:
            try:
                self.engine.stop()
            except:
                pass

# Example usage
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    def on_command(cmd):
        print(f"Command received: {cmd}")
    
    vi = VoiceInterface()
    print("Voice interface initialized. Say something...")
    vi.speak("Voice interface is ready")
    
    # Test TTS
    vi.speak("This is a test of the text to speech system.")
    print("Test complete.")
