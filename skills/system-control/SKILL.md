---
name: system-control
description: Volume, mute, screenshot, battery, lock PC, empty recycle bin.
version: 0.1.0
permissions: [os:system]
tools:
  - {name: system_control, risk: system}
---
## System Control

Volume, mute, screenshot, battery, lock PC, empty recycle bin.

## Kab use karna hai
Jab user system setting badalne ko bole: 'volume badhao', 'screenshot lo'.

## Notes
Shipped with JARVIS (local skill, trusted). Risk tier `system` — user ise
badhha sakta hai, kam karne ke liye explicit confirmation chahiye.
