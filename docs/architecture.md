# Architecture

```
                    ┌─────────────┐
  mic ──► wake ──► │ voice/      │──► text
speaker ◄── TTS ◄──┘  (STT/VAD)  │
                              ▼
                    ┌─────────────────────┐
                    │ brain/loop.py       │  agent loop
                    │  ├─ reflex.py       │  152 local rules (no LLM needed)
                    │  ├─ model_router.py │  tiered LLM chain + cost guard
                    │  └─ memory/         │  SQLite + poisoning guard
                              │ tool call
                              ▼
                    ┌─────────────────────┐
                    │ policy/__init__.py  │  THE GATE — every call passes here
                    │  L0–L3 autonomy     │  risk tiers: READ < REVERSIBLE <
                    │  taint / remote /   │  DESTRUCTIVE < SYSTEM
                    │  safe / offline     │
                              ▼
                    ┌─────────────────────┐
                    │ tools/registry.py   │  every capability is a ToolSpec
                    │ perception/         │  UIA, browser, screen, files
                    │ integrations/       │  MCP, calendar/mail, scheduler,
                    │                     │  heartbeat, telegram
                              ▼
                    ┌─────────────────────┐
                    │ core/               │  event bus, lanes, audit log,
                    │                     │  watchdog, crash reports
                    └─────────────────────┘
```

## The one rule

**Nothing executes without passing `policy.decide()`.** The reflex layer,
the LLM, the scheduler, Telegram, and MCP all funnel through the same
gate. Safe mode (`jarvis --safe`) and offline mode are enforced there too
— not sprinkled across call sites.

## Processes

- `jarvisd` (`jarvis serve`) — the service: voice loop, agent, scheduler.
  Supervised by the watchdog (Task 8.3).
- `jarvis` CLI — sends commands, runs doctor/onboard, manages skills/memory.
- HUD — web UI served by jarvisd at `/hud` (Phase 7 decision:
  web-first, Tauri deferred to v1.1).

## Data flow & privacy

- Mic audio → STT provider (cloud) **only** if the egress toggles allow it;
  offline/privacy mode kills all cloud calls centrally.
- Mail bodies and tool outputs marked `carries_external_data` enter prompts
  wrapped in `<untrusted_data>` and taint the context (above-READ tools
  then require confirmation).
- Memory facts need approval before becoming profile facts. Crash reports
  stay local unless upload is explicitly opted in.

Deeper: [THREAT_MODEL.md](THREAT_MODEL.md), [DECISION_UI.md](DECISION_UI.md),
[PERF_BUDGET.md](PERF_BUDGET.md).
