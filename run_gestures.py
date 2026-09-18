import logging
from access_os.gesture_controller import GestureController, GestureEvent
import cv2

def on_gesture(event: GestureEvent):
    """Handle detected gestures."""
    print(f"\nGesture detected: {event.name} (confidence: {event.confidence:.2f})")
    if event.hand_landmarks:
        print(f"Hand position: {event.hand_landmarks.landmark[0]}")

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Starting Gesture Controller...")
    print("Press 'q' to quit")
    print("Make sure your hand is visible to the camera")
    
    # Initialize the gesture controller
    controller = GestureController(
        enable_hand_tracking=True,
        enable_face_mesh=False,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )
    
    # Register gesture handler
    controller.register_gesture('thumbs_up', on_gesture)
    
    try:
        # Start the controller
        controller.start()
        
        # Keep the application running
        while True:
            # Get the processed frame for display
            frame = controller.get_processed_frame()
            if frame is not None:
                cv2.imshow('Gesture Controller', frame)
            
            # Break the loop on 'q' key press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up
        controller.stop()
        cv2.destroyAllWindows()
        print("Gesture controller stopped.")

if __name__ == "__main__":
    main()
