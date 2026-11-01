---
name: open-application
description: Launch a desktop application by name (Chrome, Notepad, Spotify...).
version: 0.1.0
permissions: []
tools:
  - {name: open_application, risk: reversible}
---
## Open Application

Launch a desktop application by name (Chrome, Notepad, Spotify...).

## Kab use karna hai
Jab user koi app kholne ko bole: 'chrome khol do', 'notepad open karo'.

## Notes
Shipped with JARVIS (local skill, trusted). Risk tier `reversible` — user ise
badhha sakta hai, kam karne ke liye explicit confirmation chahiye.
