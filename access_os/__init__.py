"""JARVIS (Phase 2: ``src/jarvis`` is the real package).

``access_os`` is now a set of deprecated compatibility shims — one release
of grace before removal in v1.0.0. Import from ``jarvis.*`` instead.
"""

__version__ = "0.3.0"

__all__ = ["VoiceInterface", "GestureController", "AccessOS", "AIAgent"]


def __getattr__(name):
    import warnings

    warnings.warn(
        f"access_os.{name} is deprecated; use jarvis.* instead",
        DeprecationWarning,
        stacklevel=2,
    )
    if name == "VoiceInterface":
        from jarvis.voice.interface import VoiceInterface

        return VoiceInterface
    if name == "GestureController":
        from jarvis.legacy.gestures.controller import GestureController

        return GestureController
    if name == "AccessOS":
        from jarvis.legacy.access_os_main import AccessOS

        return AccessOS
    if name == "AIAgent":
        from jarvis.brain.agent import AIAgent

        return AIAgent
    raise AttributeError(f"module 'access_os' has no attribute {name!r}")
