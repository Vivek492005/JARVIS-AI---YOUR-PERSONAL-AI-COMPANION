"""
Enhanced Gesture Controller Module for ACCESS-OS
Handles advanced hand and facial gesture recognition with multi-modal input support.
"""

import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import json
import os
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Callable, Optional, Any, Set
import logging
import threading
import time
from enum import Enum, auto
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Disable pyautogui failsafe
pyautogui.FAILSAFE = False


class GestureType(Enum):
    """Types of gestures that can be recognized."""
    SWIPE_LEFT = auto()
    SWIPE_RIGHT = auto()
    SWIPE_UP = auto()
    SWIPE_DOWN = auto()
    PINCH = auto()
    FIST = auto()
    FIVE = auto()
    POINT = auto()
    THUMBS_UP = auto()
    THUMBS_DOWN = auto()
    CUSTOM = auto()

@dataclass
class GestureEvent:
    """Represents a recognized gesture event with enhanced properties."""
    name: str
    gesture_type: GestureType
    confidence: float
    hand_landmarks: Optional[np.ndarray] = None
    face_landmarks: Optional[np.ndarray] = None
    hand_landmarks_world: Optional[np.ndarray] = None
    handness: Optional[Dict[str, float]] = None
    hand_rect: Optional[Tuple[float, float, float, float]] = None  # x, y, w, h
    timestamp: float = field(default_factory=time.time)
    hand_id: Optional[int] = None
    is_primary: bool = False


class GestureRecognitionModel:
    """Base class for gesture recognition models."""
    def __init__(self):
        self.is_active = True
        
    def process(self, frame: np.ndarray) -> List[GestureEvent]:
        raise NotImplementedError
        
    def close(self):
        self.is_active = False


class HandGestureModel(GestureRecognitionModel):
    """Handles hand gesture recognition."""
    def __init__(self, max_num_hands=2, min_detection_confidence=0.7, 
                 min_tracking_confidence=0.5):
        super().__init__()
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        self.prev_hand_landmarks = {}
        self.gesture_history = {}
        
    def process(self, frame: np.ndarray) -> List[GestureEvent]:
        events = []
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        if results.multi_hand_landmarks:
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, 
                                               results.multi_handedness):
                hand_id = id(hand_landmarks)
                landmarks = np.array([[lm.x, lm.y, lm.z] 
                                   for lm in hand_landmarks.landmark])
                
                # Get hand bounding box
                x_coords = [lm.x for lm in hand_landmarks.landmark]
                y_coords = [lm.y for lm in hand_landmarks.landmark]
                x_min, x_max = min(x_coords), max(x_coords)
                y_min, y_max = min(y_coords), max(y_coords)
                hand_rect = (x_min, y_min, x_max - x_min, y_max - y_min)
                
                # Detect gestures
                gesture_type, confidence = self._detect_gesture(landmarks, hand_id)
                
                events.append(GestureEvent(
                    name=gesture_type.name.lower(),
                    gesture_type=gesture_type,
                    confidence=confidence,
                    hand_landmarks=landmarks,
                    hand_rect=hand_rect,
                    handness={
                        'label': handedness.classification[0].label.lower(),
                        'score': handedness.classification[0].score
                    },
                    hand_id=hand_id,
                    is_primary=(hand_id == id(results.multi_hand_landmarks[0]))
                ))
                
                self.prev_hand_landmarks[hand_id] = landmarks
        
        return events
    
    def _detect_gesture(self, landmarks: np.ndarray, hand_id: int) -> Tuple[GestureType, float]:
        # Implement gesture detection logic here
        # This is a simplified example - you would expand this with more gestures
        
        # Thumb tip is landmarks[4], index finger tip is landmarks[8]
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        
        # Calculate distance between thumb and index finger
        distance = np.linalg.norm(thumb_tip - index_tip)
        
        if distance < 0.05:  # Threshold for pinch
            return GestureType.PINCH, 0.9
            
        # Add more gesture detections here...
        
        # Default to pointing gesture
        return GestureType.POINT, 0.7


class GestureController:
    """Enhanced Gesture Controller with advanced features."""
    
    def __init__(self, 
                 enable_hand_tracking: bool = True,
                 enable_face_mesh: bool = True,
                 enable_mouse_control: bool = True,
                 enable_gesture_typing: bool = True,
                 max_num_hands: int = 2,
                 min_detection_confidence: float = 0.7,
                 min_tracking_confidence: float = 0.5,
                 config_file: str = 'gesture_config.json',
                 auto_start: bool = False):
        """Initialize the gesture controller.
        
        Args:
            enable_hand_tracking: Whether to enable hand tracking
            enable_face_mesh: Whether to enable face mesh tracking
            max_num_hands: Maximum number of hands to detect
            min_detection_confidence: Minimum confidence for detection
            min_tracking_confidence: Minimum confidence for tracking
            config_file: Path to configuration file
            auto_start: Whether to automatically start background camera thread
        """
        self.logger = logging.getLogger(__name__)
        self.enable_hand_tracking = enable_hand_tracking
        self.enable_face_mesh = enable_face_mesh
        self.max_num_hands = max_num_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        
        # Initialize components
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        # Initialize models
        self.hand_gesture_model = None
        self.face_mesh = None
        self.cap = None
        self.is_running = False
        self.callbacks = {}
        self._thread = None
        self._stop_event = threading.Event()
        
        # Gesture recognition state
        self.last_gesture_time = {}
        self.gesture_cooldown = 0.5  # seconds
        self.active_gestures = set()
        self.gesture_history = []
        self.max_history = 50
        self._prev_wrist_x = None
        self._prev_wrist_time = 0.0
        
        # Mouse control
        self.enable_mouse_control = enable_mouse_control
        self.mouse_smoothing = 0.5
        self.prev_mouse_pos = None
        self.mouse_sensitivity = 1.5
        
        # Gesture typing
        self.enable_gesture_typing = enable_gesture_typing
        self.keyboard_layout = self._load_keyboard_layout()
        
        # Configuration
        self.config_file = config_file
        self.config = self._load_config()
        
        # Initialize models based on configuration
        self._initialize_models()
        
        # Start processing thread only if requested
        if auto_start:
            self.start()
    
    def _load_config(self) -> Dict:
        """Load gesture configuration from file."""
        default_config = {
            'gestures': {
                'swipe_left': {'enabled': True, 'sensitivity': 1.0},
                'swipe_right': {'enabled': True, 'sensitivity': 1.0},
                'pinch': {'enabled': True, 'sensitivity': 1.0},
                # Add more default gestures
            },
            'mouse': {
                'sensitivity': 1.5,
                'smoothing': 0.5,
                'scroll_sensitivity': 1.0
            },
            'accessibility': {
                'one_handed_mode': False,
                'high_contrast': False,
                'reduced_motion': False
            }
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return {**default_config, **json.load(f)}
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            
        return default_config
    
    def _save_config(self):
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving config: {e}")
    
    def _load_keyboard_layout(self) -> Dict[str, Tuple[float, float]]:
        """Load virtual keyboard layout."""
        # QWERTY layout as an example
        return {
            'q': (0, 0), 'w': (1, 0), 'e': (2, 0), 'r': (3, 0), 't': (4, 0),
            'a': (0, 1), 's': (1, 1), 'd': (2, 1), 'f': (3, 1), 'g': (4, 1),
            'z': (0, 2), 'x': (1, 2), 'c': (2, 2), 'v': (3, 2), 'b': (4, 2),
            'space': (2, 3, 3, 1)  # Spacebar is wider
        }
    
    def _initialize_models(self):
        """Initialize the required models and components."""
        try:
            # Initialize MediaPipe hands model
            self.mp_hands = mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=self.max_num_hands,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence
            )
            
            if self.enable_hand_tracking:
                self.hand_gesture_model = HandGestureModel(
                    max_num_hands=self.max_num_hands,
                    min_detection_confidence=self.min_detection_confidence,
                    min_tracking_confidence=self.min_tracking_confidence
                )
                
            if self.enable_face_mesh:
                self.face_mesh = self.mp_face_mesh.FaceMesh(
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
                
            self.logger.info("Initialized gesture recognition models")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize models: {e}")
            # Clean up if initialization fails
            if hasattr(self, 'hands') and self.hands:
                self.hands.close()
            self.cleanup()
            raise
    
    def register_gesture(self, 
                        name: str, 
                        callback: Callable[[GestureEvent], None],
                        cooldown: float = 1.0) -> None:
        """Register a callback for a specific gesture.
        
        Args:
            name: Name of the gesture to register
            callback: Function to call when gesture is detected
            cooldown: Minimum time between callbacks for this gesture (seconds)
        """
        self.callbacks[name] = {
            'callback': callback,
            'cooldown': cooldown
        }
        self.last_gesture_time[name] = 0
        self.logger.info(f"Registered gesture: {name}")
    
    def unregister_gesture(self, name: str) -> None:
        """Unregister a gesture callback.
        
        Args:
            name: Name of the gesture to unregister
        """
        if name in self.callbacks:
            del self.callbacks[name]
            del self.last_gesture_time[name]
            self.logger.info(f"Unregistered gesture: {name}")
    
    def start(self, camera_index: int = 0, max_retries: int = 3) -> bool:
        """Start the gesture recognition loop.
        
        Args:
            camera_index: Index of the camera to use (default: 0)
            max_retries: Maximum number of retry attempts for camera initialization
            
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.is_running:
            self.logger.warning("Gesture controller is already running")
            return True
            
        # Try to initialize the camera with retries
        for attempt in range(max_retries):
            self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)  # Use DirectShow on Windows
            
            # Test if camera is working
            if self.cap.isOpened():
                ret, _ = self.cap.read()
                if ret:
                    break  # Camera is working
                self.cap.release()
            
            self.logger.warning(f"Failed to initialize camera (attempt {attempt + 1}/{max_retries})")
            time.sleep(1)  # Wait before retrying
        else:
            self.logger.error(f"Could not initialize camera after {max_retries} attempts")
            if hasattr(self, 'cap') and self.cap:
                self.cap.release()
            return False
            
        try:
            # Set camera properties for better performance
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            self.is_running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._process_frames,
                daemon=True,
                name="GestureControllerThread"
            )
            self._thread.start()
            self.logger.info("Gesture controller started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start gesture controller: {e}")
            self.stop()
            return False
    
    def stop(self) -> None:
        """Stop the gesture recognition loop and release resources."""
        if not self.is_running:
            return
            
        self.logger.info("Stopping gesture controller...")
        self.is_running = False
        self._stop_event.set()
        
        # Wait for the thread to finish with a timeout
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
            if self._thread.is_alive():
                self.logger.warning("Thread did not stop gracefully")
        
        # Release resources in a safe order
        try:
            if hasattr(self, 'cap') and self.cap is not None:
                if self.cap.isOpened():
                    self.cap.release()
                self.cap = None
                
            if hasattr(self, 'hands') and self.hands is not None:
                self.hands.close()
                self.hands = None
                
            if hasattr(self, 'face_mesh') and self.face_mesh is not None:
                self.face_mesh.close()
                self.face_mesh = None
                
            cv2.destroyAllWindows()
            self.logger.info("Gesture controller stopped and resources released")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def process_frame(self, frame: Optional[np.ndarray] = None) -> Optional[Dict[str, Any]]:
        """Process a single frame from an external source or internal camera.
        
        Args:
            frame: Optional BGR frame. If None, grabs a frame from internal camera.
            
        Returns:
            Dictionary containing processing results
        """
        if frame is None:
            if not hasattr(self, 'cap') or not self.cap or not self.cap.isOpened():
                return None
            ret, frame = self.cap.read()
            if not ret:
                return None
            if self.config.get('debug', False):
                cv2.imshow('Gesture Controller', frame)
                cv2.waitKey(1)
        
        # Convert the BGR image to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process the frame
        results = self._process_frame(rgb_frame)
        self._detect_gestures(results, frame)
        self._draw_landmarks(frame, results)
        return results
    
    def _process_frames(self) -> None:
        """Main processing loop for gesture recognition."""
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.is_running and not self._stop_event.is_set():
            if not hasattr(self, 'cap') or self.cap is None or not self.cap.isOpened():
                self.logger.error("Camera not available")
                time.sleep(1)
                continue
                
            try:
                success, frame = self.cap.read()
                if not success:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        self.logger.error(f"Failed to capture frame after {consecutive_errors} attempts")
                        break
                    time.sleep(0.1)
                    continue
                    
                # Reset error counter on successful frame capture
                consecutive_errors = 0
                
                # Convert BGR to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Process frame with MediaPipe
                results = self._process_frame(rgb_frame)
                
                # Detect gestures
                self._detect_gestures(results, frame)
                self._draw_landmarks(frame, results)
                
            except Exception as e:
                self.logger.error(f"Error processing frame: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    self.logger.error(f"Too many consecutive errors, stopping...")
                    break
                time.sleep(0.1)
                continue
            
            # Display the frame only if debugging is enabled
            if self.config.get('debug', False):
                cv2.imshow('Gesture Controller', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
    
    def _process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """Process a single frame with MediaPipe models.
        
        Args:
            frame: Input RGB frame
            
        Returns:
            Dictionary containing processing results
        """
        results = {}
        
        # Process hands
        if self.hands:
            results['hands'] = self.hands.process(frame)
            
        # Process face mesh
        if self.face_mesh:
            results['face'] = self.face_mesh.process(frame)
            
        return results
    
    def _detect_gestures(self, results: Dict[str, Any], frame: np.ndarray) -> None:
        """Detect gestures in the processed frame.
        
        Args:
            results: Processed frame results
            frame: Original BGR frame
        """
        current_time = time.time()
        
        if 'hands' in results and results['hands'] and results['hands'].multi_hand_landmarks:
            for hand_landmarks in results['hands'].multi_hand_landmarks:
                # Check for pinch
                thumb_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP]
                index_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
                dist = np.sqrt((thumb_tip.x - index_tip.x)**2 + (thumb_tip.y - index_tip.y)**2)
                if dist < 0.06:
                    self._trigger_gesture('pinch', current_time)
                elif self._is_thumbs_up(hand_landmarks):
                    self._trigger_gesture('thumbs_up', current_time)
                
                # Check for swipe gestures based on wrist movement
                wrist = hand_landmarks.landmark[self.mp_hands.HandLandmark.WRIST]
                if self._prev_wrist_x is not None and self._prev_wrist_time > 0:
                    dt = current_time - self._prev_wrist_time
                    if 0.05 < dt < 0.6:
                        dx = wrist.x - self._prev_wrist_x
                        if dx < -0.15:
                            self._trigger_gesture('swipe_left', current_time)
                        elif dx > 0.15:
                            self._trigger_gesture('swipe_right', current_time)
                self._prev_wrist_x = wrist.x
                self._prev_wrist_time = current_time
                
    def _is_thumbs_up(self, hand_landmarks) -> bool:
        """Check if the hand is making a thumbs up gesture."""
        thumb_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP]
        thumb_mcp = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_MCP]
        index_pip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_PIP]
        index_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
        middle_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
        middle_pip = hand_landmarks.landmark[self.mp_hands.HandLandmark.MIDDLE_FINGER_PIP]
        
        # Thumb pointing up, index and middle fingers curled
        thumb_up = thumb_tip.y < thumb_mcp.y - 0.06
        fingers_curled = (index_tip.y > index_pip.y) and (middle_tip.y > middle_pip.y)
        return thumb_up and fingers_curled
    
    def _trigger_gesture(self, name: str, current_time: float) -> None:
        """Trigger a gesture callback if cooldown has passed."""
        if name not in self.callbacks:
            return
            
        last_time = self.last_gesture_time.get(name, 0)
        cooldown = self.callbacks[name]['cooldown']
        
        if current_time - last_time >= cooldown:
            event = GestureEvent(
                name=name,
                confidence=1.0  # Replace with actual confidence
            )
            
            try:
                self.callbacks[name]['callback'](event)
                self.last_gesture_time[name] = current_time
            except Exception as e:
                self.logger.error(f"Error in gesture callback '{name}': {e}")
    
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
