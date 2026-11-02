---
name: gesture-confirm
description: Thumbs-up/down camera gesture as an extra confirmation channel for JARVIS confirmations.
version: 0.1.0
permissions: [camera]
tools:
  - {name: gesture_confirm, risk: reversible}
---
## Gesture Confirm

Optional plugin (Task 7.8): answers a yes/no confirmation with a camera
gesture instead of typing/speaking.

## Kab use karna hai
Jab policy engine confirmation maange aur user ne gesture-confirm skill
enable ki ho — `gesture_confirm` tool camera kholkar thumbs-up
(haan) / thumbs-down (nahi) ka intezaar karta hai.

## Privacy
- Camera SIRF confirmation window (default 15 second) ke liye khulta hai,
  phir band ho jaata hai.
- Frames memory me process hote hain — disk par kabhi save NAHI hote.
- mediapipe/opencv install nahi hain to tool cleanly "unavailable" deta hai;
  skill optional hai, hard dependency nahi.

## Notes
Shipped with JARVIS (local skill, trusted). Risk tier `reversible` —
yeh sirf haan/nahi jawab deta hai, koi action nahi leta.
