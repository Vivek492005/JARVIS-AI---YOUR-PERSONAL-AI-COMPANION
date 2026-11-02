# Hardware Checklist (per-release, manual) — Task 8.1

Run on the target Windows machine before every release tag. Check = tested,
`—` = not applicable on this hardware.

## Audio
- [ ] Microphone: `jarvis onboard` mic step passes, noise floor sane
- [ ] Speakers: earcons audible at sane volume, quiet-hours dimming verified
- [ ] Wake word: 5/5 triggers at 1m distance in a quiet room
- [ ] Wake word: 0 false triggers in 30 min of normal room noise
- [ ] Barge-in: speaking over JARVIS interrupts cleanly

## Voice pipeline
- [ ] STT accuracy spot-check (10 English + 10 Hinglish phrases)
- [ ] p50 voice latency ≤ 1.5 s (`jarvis doctor --latency`)

## Vision / input
- [ ] Camera: gesture-confirm thumbs-up/down works (if camera present)
- [ ] Multi-monitor: HUD renders on primary display, no off-screen window
- [ ] DPI: HUD readable at 125% and 150% scaling

## System
- [ ] Tray icon appears; hotkey (Ctrl+Alt+J) summons HUD with another app focused
- [ ] Autostart (if enabled): jarvisd starts on login
- [ ] Laptop battery mode: no runaway CPU (Task Manager < 3% idle)
- [ ] Safe mode: `jarvis --safe` runs reflex + READ tools only

## Install
- [ ] Installer completes per-user (no admin prompt)
- [ ] Start-menu entry + uninstaller present
- [ ] Uninstall removes program; config/logs deletion offered, not forced
- [ ] Portable zip runs from a USB stick path with spaces in it

## Results log

| Release | Date | Machine | Tester | Notes |
|---|---|---|---|---|
| v1.0.0 | | | | |
