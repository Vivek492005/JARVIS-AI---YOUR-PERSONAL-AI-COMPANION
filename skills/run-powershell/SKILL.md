---
name: run-powershell
description: Run an allowlisted read-only PowerShell command.
version: 0.1.0
permissions: [os:shell-readonly]
tools:
  - {name: run_powershell_command, risk: system}
---
## PowerShell (read-only)

Run an allowlisted read-only PowerShell command.

## Kab use karna hai
Jab user system info nikalne ko bole jo sirf PowerShell de sakta hai.

## Notes
Shipped with JARVIS (local skill, trusted). Risk tier `system` — user ise
badhha sakta hai, kam karne ke liye explicit confirmation chahiye.
