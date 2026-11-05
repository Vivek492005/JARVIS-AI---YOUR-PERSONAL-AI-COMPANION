"""Tests for the gesture controller module."""

import sys
import unittest
from unittest.mock import MagicMock, patch

# Stub platform/heavy modules (cv2, mediapipe, pyautogui) so the unit tests
# run on any OS without camera hardware or Windows-only packages.
for _mod in ("cv2", "mediapipe", "pyautogui"):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))

import numpy as np  # noqa: E402
from access_os.gesture_controller import GestureController, GestureEvent  # noqa: E402


class TestGestureController(unittest.TestCase):
    """Test cases for the GestureController class."""

    def setUp(self):
        """Set up test fixtures."""
        # The controller binds `mp`/`cv2` at import time. The sys.modules
        # setdefault above loses when another module imported the real
        # packages first during collection (tests/hardware/test_gestures.py
        # does `pytest.importorskip("mediapipe")` at module level, and
        # hardware/ sorts before integration/). On Python 3.12 the real
        # mediapipe wheel has no `mp.solutions`, so __init__ crashes; and
        # the real cv2's imshow aborts headless (no display). Patching the
        # module globals here makes the tests independent of collection
        # order; patches auto-undo per test.
        self._mp_patcher = patch("jarvis.legacy.gestures.controller.mp", MagicMock(name="mp"))
        self._mp_patcher.start()
        self.addCleanup(self._mp_patcher.stop)
        mock_cv2 = MagicMock(name="cv2")
        mock_cv2.waitKey.return_value = ord("q")
        self._cv2_patcher = patch("jarvis.legacy.gestures.controller.cv2", mock_cv2)
        self._cv2_patcher.start()
        self.addCleanup(self._cv2_patcher.stop)
        self.gc = GestureController(enable_hand_tracking=True, enable_face_mesh=False)
        self.gc.hands = MagicMock()
        self.gc.face_mesh = None
        self.gc.cap = MagicMock()
        self.gc.cap.isOpened.return_value = True
        self.gc.cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))

        # Mock MediaPipe hands results
        self.hand_landmarks = MagicMock()
        self.hand_landmarks.landmark = [MagicMock() for _ in range(21)]
        self.hands_result = MagicMock()
        self.hands_result.multi_hand_landmarks = [self.hand_landmarks]
        self.gc.hands.process.return_value = self.hands_result

    def test_register_gesture(self):
        """Test registering a new gesture."""
        callback = MagicMock()
        self.gc.register_gesture("test_gesture", callback, cooldown=1.0)

        self.assertIn("test_gesture", self.gc.callbacks)
        self.assertEqual(self.gc.callbacks["test_gesture"]["callback"], callback)
        self.assertEqual(self.gc.callbacks["test_gesture"]["cooldown"], 1.0)

    def test_unregister_gesture(self):
        """Test unregistering a gesture."""
        callback = MagicMock()
        self.gc.register_gesture("test_gesture", callback)
        self.gc.unregister_gesture("test_gesture")

        self.assertNotIn("test_gesture", self.gc.callbacks)

    @patch("cv2.cvtColor")
    @patch("cv2.waitKey")
    def test_process_frames(self, mock_wait_key, mock_cvt_color):
        """Test the main processing loop."""
        mock_wait_key.return_value = ord("q")  # Simulate 'q' key press to exit
        mock_cvt_color.return_value = np.zeros((480, 640, 3))

        # Mock the _process_frame method to return a valid result
        with (
            patch.object(
                self.gc, "_process_frame", return_value={"hands": self.hands_result}
            ) as mock_pf,
            patch.object(self.gc, "_detect_gestures") as mock_dg,
            patch.object(self.gc, "_draw_landmarks"),
        ):
            self.gc.is_running = True  # allow the loop to execute one iteration
            self.gc.config["debug"] = True  # the 'q'-to-quit check only runs in debug mode
            self.gc._process_frames()

        # Verify that the main loop ran (one full pipeline iteration)
        self.gc.cap.read.assert_called()
        mock_pf.assert_called()
        mock_dg.assert_called()

    def test_trigger_gesture(self):
        """Test triggering a gesture callback."""
        callback = MagicMock()
        self.gc.register_gesture("test_gesture", callback)

        # Create a test event
        GestureEvent(name="test_gesture", confidence=0.9, hand_landmarks=None, face_landmarks=None)

        # Trigger the gesture
        self.gc._trigger_gesture("test_gesture", 1000.0)

        # Verify the callback was called
        callback.assert_called_once()
        self.assertEqual(self.gc.last_gesture_time["test_gesture"], 1000.0)

    def test_trigger_gesture_cooldown(self):
        """Test that gestures respect the cooldown period."""
        callback = MagicMock()
        self.gc.register_gesture("test_gesture", callback, cooldown=1.0)

        # First trigger (should work)
        self.gc._trigger_gesture("test_gesture", 1000.0)

        # Second trigger within cooldown (should be ignored)
        self.gc._trigger_gesture("test_gesture", 1000.5)

        # Verify the callback was only called once
        callback.assert_called_once()


class TestGestureEvent(unittest.TestCase):
    """Test cases for the GestureEvent dataclass."""

    def test_gesture_event_creation(self):
        """Test creation of GestureEvent objects."""
        event = GestureEvent(
            name="test_gesture", confidence=0.95, hand_landmarks=[1, 2, 3], face_landmarks=[4, 5, 6]
        )

        self.assertEqual(event.name, "test_gesture")
        self.assertEqual(event.confidence, 0.95)
        self.assertEqual(event.hand_landmarks, [1, 2, 3])
        self.assertEqual(event.face_landmarks, [4, 5, 6])


if __name__ == "__main__":
    unittest.main()
