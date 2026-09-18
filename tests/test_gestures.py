import cv2
import mediapipe as mp
import numpy as np
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_camera():
    """Test if the camera is working."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Could not open camera!")
        return False
    
    logger.info("Camera is working. Press 'q' to exit.")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            logger.error("Failed to grab frame")
            break
            
        cv2.imshow('Camera Test - Press q to exit', frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    return True

def test_hand_tracking():
    """Test hand tracking with MediaPipe."""
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Could not open camera!")
        return False
    
    logger.info("Hand tracking test. Show your hand to the camera. Press 'q' to exit.")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            logger.error("Failed to grab frame")
            break
            
        # Convert to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process the frame
        results = hands.process(rgb_frame)
        
        # Draw hand landmarks
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp.solutions.drawing_utils.draw_landmarks(
                    frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                
                # Get the coordinates of the index finger tip
                index_finger_tip = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
                h, w, c = frame.shape
                cx, cy = int(index_finger_tip.x * w), int(index_finger_tip.y * h)
                cv2.circle(frame, (cx, cy), 10, (0, 255, 0), cv2.FILLED)
        
        # Show the frame
        cv2.imshow('Hand Tracking Test - Press q to exit', frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    return True

def test_voice_recognition():
    """Test basic voice recognition."""
    try:
        import speech_recognition as sr
        
        r = sr.Recognizer()
        with sr.Microphone() as source:
            print("Speak something... (say 'hello' or 'test')")
            audio = r.listen(source, timeout=5)
            
        try:
            text = r.recognize_google(audio)
            print(f"You said: {text}")
            return True
            
        except sr.UnknownValueError:
            print("Could not understand audio")
            return False
            
        except sr.RequestError as e:
            print(f"Could not request results; {e}")
            return False
            
    except Exception as e:
        print(f"Error in voice recognition: {e}")
        return False

if __name__ == "__main__":
    print("\n=== Testing Camera ===")
    if test_camera():
        print("\n✓ Camera test passed!")
        
        print("\n=== Testing Hand Tracking ===")
        if test_hand_tracking():
            print("\n✓ Hand tracking test passed!")
        else:
            print("\n✗ Hand tracking test failed!")
    else:
        print("\n✗ Camera test failed!")
    
    print("\n=== Testing Voice Recognition ===")
    if test_voice_recognition():
        print("\n✓ Voice recognition test passed!")
    else:
        print("\n✗ Voice recognition test failed!")
    
    print("\n=== Test Complete ===")
    print("\nIf any tests failed, please check:")
    print("1. Camera is properly connected and accessible")
    print("2. Microphone is working and accessible")
    print("3. Required packages are installed (opencv-python, mediapipe, SpeechRecognition, pyaudio)")
