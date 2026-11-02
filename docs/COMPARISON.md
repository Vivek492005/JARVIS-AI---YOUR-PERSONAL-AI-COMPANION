# How JARVIS compares — Task 8.7

> An honest page, not a marketing page. Comparisons are on **architecture
> and safety design** (verifiable from this repo), not on quality claims
> we can't measure yet.

## JARVIS vs. a plain voice assistant (Siri / Google Assistant / Alexa)

| | Voice assistants | JARVIS |
|---|---|---|
| Runs your own multi-step tasks | No — fixed routines only | Yes — tool-calling agent |
| Sees and drives your desktop apps | No | Yes — UIA control surface (Windows) |
| Confirm-before-destroy | Varies, mostly implicit | Explicit Haan/Nahi gate, every time |
| Local audit log of everything it did | No | Yes — `jarvis_audit.log`, queryable |
| Works offline | No | Degraded-but-honest offline mode |
| Open source | No | Yes — MIT |

## JARVIS vs. an "AI agent" CLI tool

General-purpose coding agents are built for developers and terminals.
JARVIS is built for **a person's whole computer, by voice**:

- Voice-first (wake word, barge-in, earcons), not terminal-first.
- Safety model designed for irreversible real-world actions (trash-only
  deletes, no silent destructive timer actions), not just file edits.
- Persona + HUD + mobile PWA for non-technical users.

## What JARVIS is *not* (yet)

- Not verified on real hardware — `v1.0.0` is the first release that will be.
- No plugin marketplace yet — bundled skills only.
- No speaker verification — a TV can theoretically trigger the wake word.
- No code signing yet — expect the SmartScreen warning on v1.

If any row on this page becomes outdated, that's a docs bug — please file it.
