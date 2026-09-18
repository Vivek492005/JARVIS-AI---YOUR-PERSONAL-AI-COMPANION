# Gesture Controller Commands

ACCESS-OS uses computer vision and hand tracking (via MediaPipe) to recognize hand gestures for navigation, system control, mouse pointer tracking, and accessibility.

---

## Core System & Navigation Gestures

- **Swipe Left**  
  *Action:* Move hand quickly to the left  
  *Function:* Switch to **Gesture Mode** / Navigate backward
  
- **Swipe Right**  
  *Action:* Move hand quickly to the right  
  *Function:* Switch to **Voice Mode** / Navigate forward

- **Swipe Up**  
  *Action:* Move hand quickly upward  
  *Function:* Scroll page up

- **Swipe Down**  
  *Action:* Move hand quickly downward  
  *Function:* Scroll page down

- **Pinch (Thumb & Index Finger)**  
  *Action:* Bring thumb tip and index finger tip together (< 5cm distance)  
  *Function:* Toggle Settings Menu / Select active item / Left-click

- **Thumbs Up**  
  *Action:* Extend thumb upwards with other fingers curled  
  *Function:* Confirm action / Acknowledge prompt ("Yes" / "OK")

- **Thumbs Down**  
  *Action:* Point thumb downwards with other fingers curled  
  *Function:* Cancel / Dismiss dialog ("No" / "Back")

---

## Mouse & Pointer Controls

When mouse control is enabled (`enable_mouse_control: true`):

- **Pointing (Index Finger Extended)**  
  *Action:* Extend your index finger while keeping other fingers relaxed  
  *Function:* Controls the mouse pointer position across your display

- **Pinch Click**  
  *Action:* Quickly touch thumb and index finger together while pointing  
  *Function:* Triggers a mouse left-click at current pointer location

- **Closed Fist**  
  *Action:* Close hand into a fist  
  *Function:* Mouse click & drag / Hold selection

- **Open Palm (Five Fingers Extended)**  
  *Action:* Hold open hand facing the camera  
  *Function:* Release drag / Pause pointer tracking

---

## On-Screen UI & Mode Controls

- **ESC Key**  
  *Function:* Exit the application gracefully from the camera window
- **Camera Window ('X' Button)**  
  *Function:* Closes the camera view and safely terminates ACCESS-OS
- **Pinch in Settings Mode**  
  *Function:* Closes the settings view and returns to Idle / Home

---

## Configuration

Gesture settings are configured in `gesture_config.json` and `config.json`:

```json
{
  "enable_gesture_control": true,
  "gesture_sensitivity": 0.8,
  "enable_mouse_control": true,
  "show_camera_feed": true,
  "show_gesture_feedback": true,
  "mouse": {
    "sensitivity": 1.5,
    "smoothing": 0.5,
    "scroll_sensitivity": 1.0
  }
}
```

- **`gesture_sensitivity`**: Detection threshold sensitivity (0.1 to 1.0)
- **`enable_mouse_control`**: Enables moving the mouse pointer using hand tracking
- **`mouse.smoothing`**: Smoothing factor for pointer movement (reduces jitter)
- **`mouse.sensitivity`**: Pointer travel distance multiplier

---

## Best Practices & Tips

1. **Camera Position & Framing**:
   - Keep your camera at eye or chest level.
   - Position yourself 1.5 to 3 feet (0.5m – 1m) from the webcam.
   - Keep your entire hand inside the camera frame.

2. **Lighting Conditions**:
   - Ensure the room is well-lit with light in front of you, not directly behind you (avoid strong backlighting).
   - Natural or diffuse white light offers the most accurate landmark detection.

3. **Gesture Clarity**:
   - Perform deliberate gestures rather than rapid, continuous movements.
   - Hold a gesture (e.g. pinch or thumbs up) briefly for the cooldown period (0.5s) to register cleanly.
   - Use the visual landmark skeleton shown on your hand in the camera feed to confirm detection.

---

## Troubleshooting

- **Gestures Not Triggering:**
  - Check the green skeleton lines drawn over your hand in the window. If no lines appear, improve room lighting or adjust hand distance.
- **Mouse Jitter:**
  - Increase the `mouse.smoothing` value in `gesture_config.json` (e.g., set to `0.7` or `0.8`).
- **Accidental Triggers:**
  - Increase the gesture cooldown or lower sensitivity in configuration.
- **Multiple Hands:**
  - ACCESS-OS tracks up to 2 hands; designate your dominant hand as primary for mouse controls.
