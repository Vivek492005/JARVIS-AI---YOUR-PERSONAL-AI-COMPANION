# JARVIS — Packaging Roadmap (Windows .exe installer)

**Status:** Plan (not yet implemented) · **Priority:** P2 — starts after Plan 01 (security) and Plan 02 Phases A+B (cleanup)
**Goal:** a non-technical user downloads `JARVIS-Setup.exe`, double-clicks, answers 3 installer screens, and is talking to JARVIS — no Python, no pip, no `.env` editing by hand.

---

## 0. Tool choice (decided, with reasons)

| Option | Verdict |
|--------|---------|
| **PyInstaller (one-dir) + Inno Setup 6** | ✅ Pick this. Standard for Python Windows apps, handles tkinter well, Inno gives a real installer (start-menu entry, uninstaller, autostart option). |
| Nuitka | Faster binaries, but longer builds and trickier with mediapipe/cv2. Revisit if startup time becomes a complaint. |
| briefcase / pyapp | Immature on Windows for this dependency mix. |
| PyInstaller **one-file** | ❌ Don't. ~500MB single exe with 30s+ extract-on-launch; one-dir launches faster and updates are smaller. |

---

## Phase 0 — Prerequisites (from Plans 01 & 02, non-negotiable)

- [ ] Plan 02 Phase A+B done — dead files deleted, requirements slimmed. PyInstaller bundles every declared dependency; shipping torch "just in case" turns a ~200MB app into a ~2GB one.
- [ ] Plan 01 done — you are about to hand an `.exe` that runs PowerShell to non-technical users. The validator + confirmation gate must ship **in** v1 of the installer, not after.
- [ ] `main.py` launches cleanly from a fresh venv with no console window (`pythonw`) — already the case via the `.bat`; verify again post-cleanup.

## Phase 1 — PyInstaller build (the hard part)

1. `pip install pyinstaller`; create `packaging/jarvis.spec` (checked into the repo, not generated each time):
   - Entry: `main.py`, `console=False`, `name="JARVIS"`.
   - `datas`: `puppy.jpg`, `voice_config.json`, `config.json`, `env.example` (as template), `VOICE_COMMANDS.md`/`GESTURE_COMMANDS.md` (help).
   - `hiddenimports`: `speech_recognition`, `pyttsx3.drivers.sapi5`, `edge_tts`, `yt_dlp`, `PIL`, `numpy`, `cv2` (gestures are optional — see below).
2. **Gesture support decision:** mediapipe is the heaviest, most fragile dep under PyInstaller (DLL discovery issues are well-documented). Recommendation for v1: **ship gestures as an optional component** — build the installer without mediapipe/opencv; `run_gestures.py` stays source-only for now. Revisit in v2. This keeps v1 shippable.
3. Handle `.env`: the installer must NOT bundle the dev's `.env`. Ship `env.example`; on first launch, if no `.env` exists, the GUI shows a first-run setup dialog (paste 3 keys → writes `.env`). This replaces the "open .env in a text editor" step — critical for non-technical users.
4. Smoke test on a **clean Windows VM** (no Python installed): launch, first-run key dialog, voice test, one tool call (screenshot), TTS speaks. Log every failure — PyInstaller issues are always missing-DLL/hidden-import, never logic.
5. Expected size: ~150–300MB one-dir (post-cleanup, no mediapipe/torch). Acceptable.

**Known pain points (don't be surprised):**
- `pyttsx3` needs its SAPI5 driver bundled explicitly; test TTS on the clean VM, not the dev machine.
- `SpeechRecognition` needs PyAudio's `_portaudio` DLL — PyInstaller usually finds it; if not, add as binary.
- Windows Defender/SmartScreen **will** flag an unsigned exe. See Phase 3.

## Phase 2 — Inno Setup installer

`packaging/jarvis.iss` producing `JARVIS-Setup-v1.0.0.exe`:

- Installs to `%LOCALAPPDATA%\JARVIS` (no admin rights needed — fewer UAC prompts, fewer support tickets).
- Screens: license (MIT) → install location → options: [x] Desktop shortcut, [x] Start with Windows, [x] Install gesture support (v2; disabled in v1 with "coming soon").
- Bundles a JRE-free, Python-free runtime — everything from Phase 1.
- Proper uninstaller that removes the dir + shortcuts + autostart entry, and **asks** whether to delete `notes.txt` / `jarvis_audit.log` (user data — never silently delete).
- Version resource stamped on the exe (shows correctly in Task Manager / Add/Remove Programs).

## Phase 3 — Release pipeline (GitHub Actions)

`.github/workflows/release.yml` on `windows-latest`:

1. Trigger: push of tag `v*` (e.g. `v1.0.0`).
2. Steps: checkout → setup-python → `pip install -r requirements.txt` → run `pytest` (build fails if tests fail — this is the quality gate) → PyInstaller build → Inno Setup compile (`iscc packaging/jarvis.iss`) → upload `JARVIS-Setup-*.exe` to the GitHub Release.
3. User flow: Vivek pushes tag → ~20–40 min → release page has the installer. Zero manual steps.

**Code signing (honest note):** an EV/OV certificate costs ~$200–500/year and removes the SmartScreen warning. For v1, ship unsigned and document it: README + release notes say "Windows will show an 'Unknown publisher' warning — click More info → Run anyway." Revisit signing if/when there's revenue or broad distribution. Do NOT buy a cert for v1.

## Phase 4 — Auto-update (v2, not v1)

- Don't build a custom updater for v1. Ship v1, learn what breaks.
- v2 option: Ship a tiny `version.json` on the GitHub Release; the app checks it on launch and opens the release page when a newer version exists. No silent auto-install — the app runs shell commands; silent updates to a tool like this are a security smell.

---

## What success looks like

A friend with zero Python knowledge: downloads the exe from GitHub Releases → installs in 2 minutes → pastes 3 API keys into the first-run dialog → says "JARVIS, open Chrome" → it works. If any step needs a terminal, the phase failed.

## Order & estimates

Phase 0 (deps: Plans 01+02) → Phase 1 (2–3 sessions; most time on clean-VM debugging) → Phase 2 (1 session) → Phase 3 (1 session) → Phase 4 (later). Total: roughly 1–2 weeks of focused work, dominated by Phase 1's VM testing.
