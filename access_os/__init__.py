"""
ACCESS-OS: A Unified Assistive Operating Environment

This package provides a comprehensive accessibility layer for Windows,
enabling users with various disabilities to interact with their computer
using voice, gestures, and other assistive technologies.
"""

__version__ = "0.1.0"

# Import core components
from .voice_interface import VoiceInterface
from .gesture_controller import GestureController
from .main import AccessOS

__all__ = ['VoiceInterface', 'GestureController', 'AccessOS']
