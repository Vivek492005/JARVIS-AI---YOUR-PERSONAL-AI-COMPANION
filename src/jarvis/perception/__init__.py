"""Perception & Computer Control (Master Plan Phase 5).

JARVIS ko dekhne aur sahi tareeke se operate karne wala banana:
UI Automation, screen capture + OCR, VLM fallback, browser automation,
file intelligence, app adapters, context awareness — sab safety rails
(policy gate, audit, privacy blocklist) ke saath.

Submodules:
    privacy   — sensitive-window blocklist shared by UIA/screen (5.2/5.3)
    backends  — backend protocols + injection point (real vs fake)
    ladder    — 5.1 control-surface ladder (API > CLI > UIA > DOM > OCR > VLM)
    uia       — 5.2 UI Automation layer
    screen    — 5.3 screen capture + OCR + privacy filter
    vlm       — 5.4 VLM fallback (set-of-marks)
    browser   — 5.5 Playwright browser automation (dedicated profile)
    files     — 5.6 file intelligence (scoped workspace, dry-run, undo)
    apps      — 5.7 app adapters (VS Code, Office, Spotify, settings)
    context   — 5.8 context awareness (privacy-safe)
    postconditions — 5.9 postconditions on all action tools
    sandbox   — 5.10 agent sandbox / isolation levels
    tools     — ToolSpec registrations for every new tool
"""
