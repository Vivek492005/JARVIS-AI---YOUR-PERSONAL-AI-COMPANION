# HUD Design Spec (Task 7.2)

**Date:** 2026-11-02 · **Implements:** `src/jarvis/hud/` · **UI decision:** `docs/DECISION_UI.md`

## State → visual mapping

The HUD mirrors the agent's runtime state. One state is active at a time; the Python
`HUDStateMachine` (`src/jarvis/hud/state.py`) derives it from bus events, and the web
UI renders it. No polling — everything is event-driven over the `/events` WebSocket.

| State | Trigger events | Orb / ring | Color | Extra |
|---|---|---|---|---|
| `idle` | (initial), `SpeechStopped` with empty queue | Slow pulse, dim | Cool blue `#6ea8fe` | Minimal |
| `listening` | `WakeDetected`, `UtterancePartial` | Audio-reactive ring (mic level) | Cyan `#5ff2c8` | Live partial transcript |
| `thinking` | `AgentThinking`, `ToolRequested` | Rotating segments | Amber `#ffb454` | Step / plan chips |
| `speaking` | `SpeechStarted` | Waveform from TTS audio | White/blue `#e8f4ff` | Captions |
| `confirming` | `ConfirmationRequested` | Highlighted card over orb | Orange `#ff9f43` | Exact action + [Haan] / [Nahi] |
| `error` | `Error` | Flicker | Red `#ff5d5d` | Retry / handoff button |

Transition rules (enforced in `HUDStateMachine`, illegal transitions are ignored):
- `idle → listening` on `WakeDetected`
- `listening → thinking` on `UtteranceFinal`
- `thinking → confirming` on `ConfirmationRequested`; `confirming → thinking` on `ConfirmationAnswered`
- `thinking → speaking` on `SpeechStarted`; `speaking → idle` on `SpeechStopped`
- any → `error` on `Error`; `error → idle` on next `WakeDetected` or user dismiss
- `thinking` self-loops on `ToolRequested` / `ToolFinished` (timeline grows, state stays)

## Components

1. **Orb/ring** — Canvas 2D (no WebGL dependency for v1; Three.js upgrade path kept).
   `AnalyserNode`-style audio reactivity is fed by mic-level values pushed over WS
   (`audio_level` messages); when no mic data, the ring animates from state only.
2. **Transcript stream** — user + JARVIS turns, scrollable history (fixes the old
   300×420 fixed-card limit). `UtterancePartial` updates the live line in place.
3. **Action timeline** — every `ToolRequested`/`ToolFinished` appends
   `"Chrome khola ✓"`-style entries. The agent is always visibly doing something.
4. **Confirmation cards** — exact tool + args from `ConfirmationRequested`;
   [Haan]/[Nahi] buttons answer via `POST /command` with `!haan` / `!nahi`
   (the agent's existing pending-confirmation words).
5. **Telemetry widget** — CPU/RAM/battery from `jarvis doctor --json` (polled 5s,
   collapsible, off by default on battery-saver).
6. **Overlay modes** — compact orb (always-on-top via Tauri shell in v1.1; in v1.0 a
   small browser window) ↔ expanded panel ↔ fullscreen. Pure CSS, no reload.
7. **Taskbar + tray** — v1.1 Tauri shell (see DECISION_UI.md). v1.0: PWA install.
8. **Accessibility** — captions always available (transcript doubles as captions),
   high-contrast theme toggle, `prefers-reduced-motion` respected (orb becomes a
   static dot), full keyboard operation (Tab order, Enter to confirm).

## Done-when (and what we can verify headless)

- [x] All 6 states reachable via events; illegal transitions rejected (unit-tested)
- [x] WS event → UI message mapping is 1:1 with `event_to_dict` (contract test)
- [x] Static assets served with correct MIME + auth on `/hud` (HTTP test)
- [ ] 60fps / <3% idle CPU — needs a real browser on the target machine
- [ ] Visual check of orb/transcript/timeline — needs a human eye

## Files

- `src/jarvis/hud/__init__.py`, `state.py` — state machine
- `src/jarvis/hud/static/index.html`, `styles.css`, `app.js` — the web UI
- `src/jarvis/hud/static/manifest.json`, `sw.js` — PWA (7.9)
- Served from `jarvisd` at `/hud` (authenticated, same token as `/state`)
