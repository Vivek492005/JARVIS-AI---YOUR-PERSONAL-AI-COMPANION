# JARVIS — Cleanup Plan

**Status:** Plan (not yet implemented) · **Priority:** P1 — do before packaging (Plan 03 depends on it)
**Verified:** every claim below was checked with `grep` against the cloned repo on 2026-10-30.

---

## Phase A — Delete dead files (safe, zero references)

These files are imported **nowhere** — not by code, not by `.bat` files, not by docs:

| File | Lines | What it is |
|------|-------|------------|
| `access_os/fixed_voice_interface.py` | 152 | Older "fixed" copy of the voice interface |
| `access_os/voice_interface_new.py` | 150 | Another abandoned rewrite attempt |
| `access_os/gesture_controller_fixed.py` | 233 | Abandoned "fixed" gesture controller |

**Steps:**
1. `grep -rn "fixed_voice_interface\|voice_interface_new\|gesture_controller_fixed"` → confirm zero hits (already verified; re-run at implementation time).
2. Delete the three files. Commit: `chore: remove abandoned duplicate modules (zero references)`.
3. Add a repo rule to `CONTRIBUTING.md`: no `*_fixed.py` / `*_new.py` copies — fix in place or use a branch.

**Risk:** none. **Effort:** 10 minutes.

---

## Phase B — Slim the dependency list (biggest packaging win)

`requirements.txt` declares packages that are **imported nowhere** in the codebase:

- `torch`, `torchvision`, `torchaudio` (~2 GB install)
- `transformers`
- `openai-whisper` (STT actually uses `recognize_google`; whisper is never imported)
- `flask`, `flask-socketio` (no web server exists in the code)
- `pandas`, `keyboard`, `pynput`, `pywinauto`, `pygetwindow`

**Steps:**
1. Split into two files:
   - `requirements.txt` — only what `grep` proves is imported (openai, httpx, SpeechRecognition, pyttsx3, edge-tts, yt-dlp, opencv-python, mediapipe, numpy, pyautogui, python-dotenv, Pillow, python-dateutil, pywin32, pytest stack, linters).
   - `requirements-optional.txt` — the removed ones, commented with *why* each was dropped and what would need it back (e.g. "whisper — re-add if offline STT is implemented per roadmap").
2. Fresh-venv test: `python -m venv`, `pip install -r requirements.txt`, `python -m pytest tests/ -x`, launch `main.py` to the widget stage. If anything breaks, the grep missed a dynamic import — fix the list, don't just re-add blindly.
3. Document the decision in the README install section (one line: "heavy ML/web deps were removed; see requirements-optional.txt").

**Expected win:** install goes from multi-GB + 10-minute pip builds to a few hundred MB. This is a hard dependency for Plan 03 — PyInstaller bundles *everything* in requirements.

**Risk:** low, guarded by the fresh-venv test. **Effort:** 1 hour.

---

## Phase C — Unify the two command engines (the real cleanup)

**Current routing** (`VoiceInterface.execute_text_command` → `VoiceCommandProcessor.process`):

1. Regex match against ~50 legacy patterns → 2. Fuzzy match (score > 78) → 3. LLM `AIAgent` fallback → 4. Google search fallback

**The problem isn't the pipeline — the pipeline is actually good design** (deterministic fast-path + LLM fallback + search last resort). The problem is **duplicated action implementations**: both the regex layer (`_action_take_screenshot`, `_action_lock_pc`, …) and `AIAgent` (`execute_system_control`, …) implement the same ~15 OS actions independently. Two copies to maintain, two copies to secure (Plan 01's validator must cover both).

**Target architecture:**

```
User text/voice
      │
VoiceCommandProcessor.process()   ← keeps stages 1,2,4 (routing only)
      │ regex / fuzzy hit
      ▼
Action executors (single home)    ← AIAgent.execute_* methods move here,
      │                              e.g. access_os/actions.py
      ▼
command_policy validator (Plan 01)
      │
OS / tools
```

**Steps:**
1. Create `access_os/actions.py`; move all `execute_*` methods from `AIAgent` into it as standalone functions (pure: input args → result string, no LLM state).
2. `AIAgent._dispatch_tool_call` calls into `actions.py` (thin wrapper, unchanged behavior).
3. Rewrite the ~50 `VoiceCommandProcessor._action_*` methods as thin adapters that call the same `actions.py` functions — delete the duplicated OS-manipulation code.
4. Keep stages 1/2/4 in the processor; stage 3 (LLM) stays as the intelligent fallback. Update the README "How It Works Internally" section with this diagram so contributors understand the routing.
5. Run the full test suite + a manual smoke list (open app, screenshot, volume, note save/read, download-audio dry run).

**What NOT to do:** don't delete the regex layer — it's the latency fast-path (no API round-trip for "volume up") and the offline story. Formalize it, don't remove it.

**Risk:** medium — behavior must stay identical; guard with tests + smoke list. **Effort:** one focused session.

---

## Phase D — Entry points and launch scripts

Current state: **three** entry points, undocumented which to use when.

| Entry | File | What it does |
|-------|------|--------------|
| GUI companion | `main.py` | tkinter widget + voice (the real product) |
| ACCESS-OS unified | `access_os/main.py` | voice + gesture CLI (older concept, wake word "access") |
| Gestures standalone | `run_gestures.py` | gesture controller demo |

Plus `Launch_Saarthi.bat` (wrong name, hardcoded `e:\Btech Essentials\JARVIS` path — breaks on every other machine).

**Steps:**
1. Decide: is ACCESS-OS a separate product or history? Recommendation: keep `access_os/main.py` but mark it clearly in README as "legacy unified CLI (experimental)"; the product entry is `main.py`.
2. Rename `Launch_Saarthi.bat` → `Launch_JARVIS.bat`; replace the hardcoded path with `%~dp0` (the bat's own directory) so it works from anywhere:
   ```bat
   cd /d "%~dp0"
   ```
3. Make `install.bat` idempotent and path-independent (it mostly is; verify `.venv` creation works when the repo lives under a path with spaces).
4. README "Running JARVIS" section: one table — GUI (recommended), CLI, gestures-only — with the exact command for each.

**Risk:** low. **Effort:** 1 hour.

---

## Order of execution

**A → B → D → C.** A and B are mechanical and unblock everything. D is quick. C is the deep refactor — do it last, on the clean tree, with Plan 01's validator already in place so the unified executors are secured once, not twice.
