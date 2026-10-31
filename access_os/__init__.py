"""
ACCESS-OS: A Unified Assistive Operating Environment

This package provides a comprehensive accessibility layer for Windows,
enabling users with various disabilities to interact with their computer
using voice, gestures, and other assistive technologies.
"""

__version__ = "0.1.0"

# NOTE: imports are lazy (PEP 562) so that lightweight modules like
# access_os.command_policy and access_os.ai_agent can be imported — and
# unit-tested — without pulling in heavy optional dependencies
# (speech_recognition, pyttsx3, cv2, mediapipe).
__all__ = ['VoiceInterface', 'GestureController', 'AccessOS', 'AIAgent']


def __getattr__(name):
    if name == "VoiceInterface":
        from .voice_interface import VoiceInterface
        return VoiceInterface
    if name == "GestureController":
        from .gesture_controller import GestureController
        return GestureController
    if name == "AccessOS":
        from .main import AccessOS
        return AccessOS
    if name == "AIAgent":
        from .ai_agent import AIAgent
        return AIAgent
    raise AttributeError(f"module 'access_os' has no attribute {name!r}")
