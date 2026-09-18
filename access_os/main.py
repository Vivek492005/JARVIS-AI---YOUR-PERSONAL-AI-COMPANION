"""
ACCESS-OS Main Application

This module provides the main entry point for the ACCESS-OS application,
which integrates voice control, gesture recognition, and other accessibility
features into a unified interface.
"""

import sys
import logging
import argparse
from typing import Optional, Dict, Any, List

from .voice_interface import VoiceInterface, VoiceCommand
from .gesture_controller import GestureController, GestureEvent


class AccessOS:
    """Main application class for ACCESS-OS."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the ACCESS-OS application.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.voice_interface = VoiceInterface(
            wake_word=self.config.get('wake_word', 'access')
        )
        
        self.gesture_controller = GestureController(
            enable_hand_tracking=self.config.get('enable_hand_tracking', True),
            enable_face_mesh=self.config.get('enable_face_mesh', True),
            max_num_hands=self.config.get('max_num_hands', 2)
        )
        
        # Application state
        self.is_running = False
        self.modules = {}
        
    def setup_logging(self):
        """Configure application logging."""
        log_level = self.config.get('log_level', logging.INFO)
        log_file = self.config.get('log_file', 'access_os.log')
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_file)
            ]
        )
        
        # Suppress some noisy loggers
        logging.getLogger('comtypes').setLevel(logging.WARNING)
        logging.getLogger('PIL').setLevel(logging.WARNING)
        
    def initialize(self):
        """Initialize all components and register callbacks."""
        self.logger.info("Initializing ACCESS-OS...")
        
        # Register voice command handlers
        self.voice_interface.start_listening(self._on_voice_command)
        
        # Register gesture handlers
        self.gesture_controller.register_gesture(
            'thumbs_up',
            self._on_thumbs_up_gesture,
            cooldown=2.0
        )
        
        # Add more gesture handlers here
        
        self.logger.info("ACCESS-OS initialized successfully")
    
    def _on_voice_command(self, command: VoiceCommand):
        """Handle voice commands.
        
        Args:
            command: The recognized voice command
        """
        self.logger.info(f"Voice command: {command.text}")
        
        # Process the command (add your command processing logic here)
        if "hello" in command.text.lower():
            self.voice_interface.speak("Hello! How can I assist you today?")
        elif "time" in command.text.lower():
            from datetime import datetime
            current_time = datetime.now().strftime("%I:%M %p")
            self.voice_interface.speak(f"The current time is {current_time}")
        elif "date" in command.text.lower():
            from datetime import datetime
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            self.voice_interface.speak(f"Today is {current_date}")
        else:
            self.voice_interface.speak("I'm not sure how to help with that yet.")
    
    def _on_thumbs_up_gesture(self, event: GestureEvent):
        """Handle thumbs up gesture.
        
        Args:
            event: The gesture event
        """
        self.logger.info(f"Gesture detected: {event.name}")
        self.voice_interface.speak("Thumbs up detected!")
    
    def run(self):
        """Run the main application loop."""
        if self.is_running:
            self.logger.warning("ACCESS-OS is already running")
            return
            
        self.is_running = True
        self.logger.info("Starting ACCESS-OS...")
        
        try:
            # Start the gesture controller
            self.gesture_controller.start()
            
            # Keep the main thread alive
            while self.is_running:
                try:
                    # Main loop can be used for periodic tasks
                    # or just sleep to reduce CPU usage
                    import time
                    time.sleep(1)
                    
                except KeyboardInterrupt:
                    self.logger.info("Shutdown requested by user")
                    break
                except Exception as e:
                    self.logger.error(f"Error in main loop: {e}", exc_info=True)
                    time.sleep(1)  # Prevent tight loop on errors
                    
        except Exception as e:
            self.logger.critical(f"Fatal error: {e}", exc_info=True)
            
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Shutdown the application gracefully."""
        if not self.is_running:
            return
            
        self.logger.info("Shutting down ACCESS-OS...")
        self.is_running = False
        
        # Stop all components
        self.voice_interface.stop_listening()
        self.gesture_controller.stop()
        
        self.logger.info("ACCESS-OS has been shut down")
    
    def __enter__(self):
        """Context manager entry."""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='ACCESS-OS: A Unified Assistive Operating Environment')
    
    # Add command line arguments
    parser.add_argument('--wake-word', type=str, default='access',
                       help='Wake word for voice commands (default: access)')
    parser.add_argument('--log-level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Logging level (default: INFO)')
    parser.add_argument('--no-gestures', action='store_true',
                       help='Disable gesture recognition')
    
    return parser.parse_args()


def main():
    """Main entry point for the ACCESS-OS application."""
    args = parse_arguments()
    
    # Configure the application
    config = {
        'wake_word': args.wake_word,
        'log_level': getattr(logging, args.log_level, logging.INFO),
        'enable_hand_tracking': not args.no_gestures,
        'enable_face_mesh': not args.no_gestures
    }
    
    # Create and run the application
    with AccessOS(config) as app:
        try:
            app.run()
        except Exception as e:
            logging.critical(f"Unhandled exception: {e}", exc_info=True)
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
