# UI Technology Decision (Task 7.1)

**Date:** 2026-11-02 · **Status:** decided · **Applies to:** Phase 7+

## The decision

| Layer | Choice | Since |
|---|---|---|
| **HUD content** | Web UI (HTML/CSS/JS) served by `jarvisd` | v0.9.0 |
| **Desktop shell** | Browser window / PWA for v1.0 → **Tauri** native shell in v1.1+ | v1.0 / v1.1 |
| **Legacy** | tkinter `gui.py` frozen — works, no new features | — |

In short: the HUD is a **web client of `jarvisd`** (Task 2.4's FastAPI + `/events` WebSocket + token auth already exist).
The same codebase serves desktop and the mobile PWA (Task 7.9). Tauri becomes a thin
native shell around that web UI when we need taskbar/tray/global-hotkey (F-16) —
not a rewrite.

## Why not Tauri-first (the plan's recommendation)

The plan recommended Tauri for its small binary and web-tech visuals. That is still
the right *destination*, but starting there is wrong for v1.0:

1. **We already built the transport.** Task 2.4 gave us FastAPI, `/health`, `/state`,
   `/command`, and an authenticated `/events` WebSocket. A web HUD plugs straight in —
   zero new IPC, zero new auth to design.
2. **One codebase, two surfaces.** The mobile companion (7.9) needs a web UI anyway.
   Building the HUD as a PWA gives us desktop + mobile from day one instead of
   maintaining Tauri-desktop *and* a separate mobile client.
3. **Verifiable here.** A web UI is testable headless (HTTP test client asserts routes,
   static assets, WS event flow). Tauri needs a Rust toolchain and a Windows build to
   verify anything — we have neither on this machine.
4. **The "Iron Man" visuals need web tech regardless.** Three.js orb, Canvas
   audio-reactive ring, shader backgrounds — tkinter cannot do any of this
   (F-16/F-17 stay as documented tkinter limitations).

Tauri is **deferred, not rejected**: v1.1 wraps the proven web UI in a Tauri shell for
tray icon, global summon hotkey, always-on-top overlay, and auto-updates. No HUD code
changes needed — only the shell around it.

## Why not keep tkinter

`gui.py` (395 lines, `overrideredirect(True)` frameless widget) works but:
- No taskbar presence, no tray icon, no Alt+Tab (F-16) — needs a native shell anyway.
- Cannot render the HUD spec (7.2): no WebGL/Canvas-grade visuals, transcript stream
  would be a second implementation.
- Brand mismatch history (F-17).

It stays as a **frozen fallback**: `python gui.py` keeps working for zero-dep setups,
but all new UI work targets the web HUD.

## Why not Electron / PyQt

- **Electron:** heaviest option; we get the same web UI without shipping Chromium.
- **PyQt6/QML:** Python-only is nice, but QML can't match Three.js/Canvas for the
  7.2 visual spec, and it doesn't help the mobile story at all.

## Consequences

- `src/jarvis/hud/` owns the web UI: static files + a Python HUD state machine that
  mirrors bus events into the 6 HUD states (7.2).
- `src/jarvis/server/api.py` serves `/hud` (static) — authenticated like `/state`.
- PWA manifest + service worker ship with the HUD (7.9).
- Control center (7.7) and onboarding (7.6) are HUD pages + JSON APIs, not new apps.
- Revisit trigger: if the web HUD can't hit 60fps / <3% idle on the target machine,
  Tauri's timeline moves up; the UI code doesn't change.
