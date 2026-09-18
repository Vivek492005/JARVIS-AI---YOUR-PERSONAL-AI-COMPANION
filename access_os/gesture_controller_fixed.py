"""
Gesture Controller Module for ACCESS-OS
Handles hand and facial gesture recognition for alternative input methods.
"""

import cv2
import mediapipe as mp
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Dict, Callable, Optional, Any
import logging
import threading
import time


@dataclass
class GestureEvent:
    """Represents a recognized gesture event."""
    name: str
    confidence: float
    hand_landmarks: Optional[np.ndarray] = None
    face_landmarks: Optional[np.ndarray] = None


class GestureController:
    """Handles gesture recognition using computer vision."""
    
    def __init__(self, 
                 enable_hand_tracking: bool = True,
                 enable_face_mesh: bool = True,
                 min_detection_confidence: float = 0.7,
                 min_tracking_confidence: float = 0.5):
        """Initialize the gesture controller.
        
        Args:
            enable_hand_tracking: Whether to enable hand tracking
            enable_face_mesh: Whether to enable face mesh detection
            min_detection_confidence: Minimum confidence for detection
            min_tracking_confidence: Minimum confidence for tracking
        """
        self.enable_hand_tracking = enable_hand_tracking
        self.enable_face_mesh = enable_face_mesh
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        
        # MediaPipe instances
        self.mp_hands = mp.solutions.hands
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        # Initialize MediaPipe solutions
        self.hands = None
        self.face_mesh = None
        
        # Threading
        self.is_running = False
        self.processing_thread = None
        self.cap = None
        
        # Callbacks
        self.gesture_handlers = {}
        
        # Logger
        self.logger = logging.getLogger(__name__)
        
    def register_gesture(self, gesture_name: str, handler: Callable[[GestureEvent], None]) -> None:
        """Register a callback for a specific gesture.
        
        Args:
            gesture_name: Name of the gesture to handle
            handler: Callback function that takes a GestureEvent
        """
        self.gesture_handlers[gesture_name] = handler
        
    def start(self) -> None:
        """Start the gesture recognition thread."""
        if self.is_running:
            return
            
        # Initialize MediaPipe instances
        if self.enable_hand_tracking:
            self.hands = self.mp_hands.Hands(
                max_num_hands=2,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence
            )
            
        if self.enable_face_mesh:
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence
            )
            
        # Initialize video capture
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("Could not open video capture device")
            
        # Start processing thread
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._process_frames, daemon=True)
        self.processing_thread.start()
        self.logger.info("Gesture controller started")
        
    def stop(self) -> None:
        """Stop the gesture recognition thread."""
        self.is_running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=1.0)
            
        if self.cap:
            self.cap.release()
            
        if self.hands:
            self.hands.close()
            
        if self.face_mesh:
            self.face_mesh.close()
            
        self.logger.info("Gesture controller stopped")
        
    def _process_frames(self) -> None:
        """Main processing loop for gesture recognition."""
        while self.is_running and self.cap.isOpened():
            success, frame = self.cap.read()
            if not success:
                continue
                
            # Convert the BGR image to RGB
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process with MediaPipe
            results = {}
            
            if self.enable_hand_tracking and self.hands:
                results['hands'] = self.hands.process(image)
                
            if self.enable_face_mesh and self.face_mesh:
                results['face'] = self.face_mesh.process(image)
                
            # Process results and trigger callbacks
            self._process_results(results)
            
            # Draw landmarks for visualization
            self._draw_landmarks(frame, results)
            
            # Show the frame (for debugging)
            cv2.imshow('Gesture Controller', frame)
            if cv2.waitKey(5) & 0xFF == ord('q'):
                break
                
    def _process_results(self, results: Dict[str, Any]) -> None:
        """Process detection results and trigger callbacks."""
        # Example: Detect thumbs up
        if 'hands' in results and results.hands.multi_hand_landmarks:
            for hand_landmarks in results.hands.multi_hand_landmarks:
                # Simple thumbs up detection
                thumb_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP]
                index_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
                
                if thumb_tip.y < index_tip.y:
                    event = GestureEvent(
                        name="thumbs_up",
                        confidence=0.9,
                        hand_landmarks=hand_landmarks
                    )
                    self._trigger_gesture(event)
                    
    def _trigger_gesture(self, event: GestureEvent) -> None:
        """Trigger callbacks for the detected gesture."""
        if event.name in self.gesture_handlers:
            try:
                self.gesture_handlers[event.name](event)
            except Exception as e:
                self.logger.error(f"Error in gesture handler: {e}")
                
    def _draw_landmarks(self, frame: np.ndarray, results: Dict[str, Any]) -> None:
        """Draw landmarks on the frame for visualization."""
        # Draw hand landmarks
        if 'hands' in results and results['hands'].multi_hand_landmarks:
            for hand_landmarks in results['hands'].multi_hand_landmarks:
                self.mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_drawing_styles.get_default_hand_landmarks_style(),
                    self.mp_drawing_styles.get_default_hand_connections_style()
                )
                
        # Draw face landmarks
        if 'face' in results and results['face'].multi_face_landmarks:
            for face_landmarks in results['face'].multi_face_landmarks:
                self.mp_drawing.draw_landmarks(
                    image=frame,
                    landmark_list=face_landmarks,
                    connections=self.mp_face_mesh.FACEMESH_TESSELATION,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=self.mp_drawing_styles
                        .get_default_face_mesh_tesselation_style()
                )
    
    def __del__(self):
        """Cleanup resources."""
        self.stop()


# Example usage
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    def on_gesture(event: GestureEvent):
        print(f"Gesture detected: {event.name} (confidence: {event.confidence:.2f})")
    
    # Create and start the gesture controller
    controller = GestureController()
    controller.register_gesture('thumbs_up', on_gesture)
    
    try:
        controller.start()
        print("Gesture controller running. Press 'q' to quit.")
        
        # Keep the main thread alive
        while controller.is_running:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        controller.stop()
