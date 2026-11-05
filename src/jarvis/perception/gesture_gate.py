"""Gesture confirmation gate (Master Plan Task 7.8).

Wraps the legacy MediaPipe gesture controller as an *optional* confirmation
channel: when the policy engine needs a yes/no and the user has the
gesture-confirm skill enabled, a thumbs-up/down in front of the camera
answers it.

Privacy rules (from the plan):
- Camera opens ONLY for the confirmation window (default 15 s), then closes.
- Frames are processed in memory and never written to disk.
- The module degrades cleanly when mediapipe/opencv aren't installed —
  the skill is optional, not a hard dependency.

The controller factory is injectable so tests run headless without a camera.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)

CONFIRM_TIMEOUT_S = 15.0


def gesture_available() -> Tuple[bool, str]:
    """Is the optional gesture stack installed?"""
    missing = []
    for mod in ("mediapipe", "cv2", "numpy"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return False, f"optional deps missing: {', '.join(missing)}"
    # Importing mediapipe is NOT enough: mediapipe >= 0.10.21 wheels for
    # Python 3.12+ ship tasks-only (no mp.solutions), and 1.x removed it
    # entirely. The legacy controller needs mp.solutions.hands/face_mesh,
    # so verify it actually exists — otherwise the skill must degrade to
    # "unavailable" instead of crashing mid-confirmation with AttributeError.
    try:
        import mediapipe as _mp

        if not hasattr(_mp, "solutions"):
            return False, (
                "mediapipe installed but mp.solutions missing in this build (use Python 3.11)"
            )
    except ImportError:
        return False, "optional deps missing: mediapipe"
    return True, ""


def _default_controller():
    """Build the legacy GestureController (camera NOT started yet)."""
    from jarvis.legacy.gestures.controller import GestureController

    return GestureController(
        enable_hand_tracking=True,
        enable_face_mesh=False,
        enable_mouse_control=False,
        enable_gesture_typing=False,
        auto_start=False,
    )


def await_gesture(
    timeout_s: float = CONFIRM_TIMEOUT_S,
    controller_factory: Optional[Callable[[], object]] = None,
) -> str:
    """Open the camera, wait for a thumbs-up/down, close the camera.

    Returns "haan" | "nahi" | "timeout" | "unavailable: <reason>".
    Frames are never saved — the legacy controller processes them in
    memory and the capture device is released in a finally block.
    """
    ok, reason = gesture_available()
    if ok and controller_factory is None:
        controller_factory = _default_controller
    if controller_factory is None:
        return f"unavailable: {reason}"

    controller = controller_factory()
    result = "timeout"
    deadline = time.time() + timeout_s
    try:
        # Legacy API: register_gesture(name, callback, cooldown) /
        # unregister_gesture(name) / start(camera_index) / stop().
        seen: List[str] = []
        for gesture in ("thumbs_up", "thumbs_down"):
            controller.register_gesture(  # type: ignore[attr-defined]
                gesture, lambda ev, g=gesture: seen.append(g), cooldown=0.2
            )
        controller.start()  # type: ignore[attr-defined]
        while time.time() < deadline and not seen:
            time.sleep(0.1)
        if seen:
            result = "haan" if seen[0] == "thumbs_up" else "nahi"
    except Exception as e:
        logger.warning("gesture confirm failed: %s", e)
        result = f"unavailable: {e}"
    finally:
        try:
            controller.unregister_gesture("thumbs_up")  # type: ignore[attr-defined]
            controller.unregister_gesture("thumbs_down")  # type: ignore[attr-defined]
            controller.stop()  # type: ignore[attr-defined]
        except Exception as e:
            logger.debug("gesture controller stop: %s", e)
    return result
