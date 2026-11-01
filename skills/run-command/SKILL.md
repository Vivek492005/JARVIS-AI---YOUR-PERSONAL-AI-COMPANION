---
name: run-command
description: Run an allowlisted diagnostic (ipconfig, disk_free).
version: 0.1.0
permissions: [os:exec-allowlisted]
tools:
  - {name: run_command, risk: read}
---
## Diagnostics

Run an allowlisted diagnostic (ipconfig, disk_free).

## Kab use karna hai
Jab user network/disk diagnostic chahe.

## Notes
Shipped with JARVIS (local skill, trusted). Risk tier `read` — user ise
badhha sakta hai, kam karne ke liye explicit confirmation chahiye.
