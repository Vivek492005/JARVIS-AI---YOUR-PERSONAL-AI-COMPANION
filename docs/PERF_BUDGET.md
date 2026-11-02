# Performance Budget — Task 8.2

Targets from the Master Plan, with measured values where we have them.
"Measured" = this dev VM (Linux, headless). **Windows numbers are TBD** —
they get filled in during the v1.0.0 real-hardware run (see
`docs/HARDWARE_CHECKLIST.md`).

| Metric | Plan target | Measured (Linux VM) | Status |
|---|---|---|---|
| Cold start — CLI (`jarvis --help`) | < 3 s | ~0.3 s | ✅ well inside |
| Cold start — full voice pipeline | < 6 s | TBD (needs mic/audio) | ⏳ hardware |
| Idle RAM (cloud mode, jarvisd) | < 300 MB | TBD (needs service run) | ⏳ hardware |
| Idle CPU | < 3% | TBD (needs service run) | ⏳ hardware |
| p50 voice latency (speech → action) | ≤ 1.5 s | TBD (needs mic + provider) | ⏳ hardware |
| Install size (no local models) | < 500 MB | TBD (needs PyInstaller build) | ⏳ build |
| Reflex match (in-process) | < 0.5 s | < 0.05 s | ✅ well inside |

## How we stay inside budget

- **Lazy imports:** heavy modules (`torch`, `mediapipe`, `cv2`, XTTS, `pyttsx3`)
  are imported only on first use, never at CLI startup. `jarvis --help`
  imports nothing beyond argparse + the command registry.
- **No framework tax:** the CLI is plain argparse; the service is FastAPI
  started only by `jarvis serve`.
- **Profiling:** `python scripts/profile_startup.py [args...]` dumps a
  cProfile report of any CLI invocation — use it before v1.0.0 to catch
  regressions.
- **Gate:** `tests/unit/test_phase8_perf.py` fails the build if CLI cold
  start exceeds 10 s or a reflex match exceeds 0.5 s (generous CI-safe
  bounds; the plan targets are stricter and documented above).

## Latency budget for the voice path (design)

```
mic frame → VAD → STT → reflex/LLM → policy gate → TTS → speaker
              └─ p50 target: ≤ 1.5 s end-to-end (cloud STT+LLM) ─┘
```

`jarvis doctor --latency` reports the live breakdown on the user's machine.
