---
name: download-media
description: Download audio/video from a URL or search term.
version: 0.1.0
permissions: [network:*, disk:downloads]
tools:
  - {name: download_media, risk: reversible}
---
## Download Media

Download audio/video from a URL or search term.

## Kab use karna hai
Jab user gaana/video download karne ko bole.

## Notes
Shipped with JARVIS (local skill, trusted). Risk tier `reversible` — user ise
badhha sakta hai, kam karne ke liye explicit confirmation chahiye.
