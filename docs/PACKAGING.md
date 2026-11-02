# Packaging & Release Pipeline — Task 8.4

> **Honesty note:** everything in this doc except the static checks has
> **never run on real Windows**. The first real build is the `v1.0.0` tag
> build on the release machine (per the standing rule: first packaging test
> = v1.0.0 tag build on real hardware). Until then, "works" means "passes
> static validation", not "produces a working installer".

## Pipeline overview

```
git tag v1.0.0 && git push origin v1.0.0
        │
        ▼  .github/workflows/release.yml  (windows-latest, ~25-40 min)
┌─────────────────────┐
│ quality gate        │  pure-python safety tests (tests/security + policy)
├─────────────────────┤
│ pyinstaller         │  packaging/jarvis.spec → dist/JARVIS/JARVIS.exe
├─────────────────────┤
│ smoke test          │  JARVIS.exe --self-test
├─────────────────────┤
│ portable zip        │  scripts/build_portable.py → JARVIS-portable-vX.Y.Z.zip
│ + SHA256SUMS.txt    │
├─────────────────────┤
│ Inno Setup          │  iscc packaging/jarvis.iss → JARVIS-Setup-vX.Y.Z.exe
├─────────────────────┤
│ GitHub Release      │  installer + portable zip + SHA256SUMS.txt attached
└─────────────────────┘
```

## Installer design (from plans/03-packaging-roadmap.md)

- **Per-user install**, `%LOCALAPPDATA%\JARVIS` — no admin/UAC prompt.
- Start-menu entry, optional desktop icon, optional autostart (Task
  Scheduler runs `jarvisd` under the watchdog, Task 8.3).
- Uninstaller removes the program; deleting config/logs is **offered, not
  forced**.
- **Unsigned v1**: SmartScreen shows "Unknown publisher" — the release notes
  explain More info → Run anyway. Code signing revisited with revenue.
- **Portable zip**: unzip-and-run, no install; for USB sticks and locked-down
  machines.

## Static validation (runs anywhere)

```bash
python scripts/lint_packaging.py   # spec parses, datas exist, iss sane, workflow valid
```

This caught a real bug during Phase 8: `packaging/jarvis.spec` listed a
`../config.json` datas entry for a file that doesn't exist — the build would
have failed on Windows. Removed.

## Auto-update (client side)

`src/jarvis/core/updater.py`:

1. `check_for_update(current)` queries the GitHub Releases API (best-effort;
   network failure = silent None).
2. If a newer tag exists, the user is offered the installer — **never
   auto-installed**.
3. After download, `verify_sha256()` checks the file against the release's
   `SHA256SUMS.txt`. Mismatch = abort + warn (fail-closed).
4. Only `https://` asset URLs are fetched.

## What the v1.0.0 hardware run must prove

See `docs/HARDWARE_CHECKLIST.md` (Install section) plus:

- [ ] `pyinstaller packaging/jarvis.spec` completes on the release machine
- [ ] `JARVIS.exe --self-test` passes
- [ ] `iscc packaging/jarvis.iss` produces the setup exe
- [ ] `scripts/build_portable.py --version 1.0.0` zips correctly
- [ ] SHA256SUMS.txt verifies with `certutil -hashfile`
- [ ] The GitHub Release shows installer + zip + sums attached
- [ ] Auto-update check finds the release from an older install
