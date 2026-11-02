# Release Checklist — Task 8.5

Run top-to-bottom for every release tag. Nothing ships with an unchecked box.

## 1. Code freeze & gates (on the release machine)

- [ ] `git status` clean; HEAD is the intended commit
- [ ] Full suite green (excluding the documented pre-existing failures):
      `python -m pytest tests/ -m "not hardware and not live"`
- [ ] Coverage gate: `python scripts/check_coverage.py` → PASSED
- [ ] Packaging lint: `python scripts/lint_packaging.py` → PASSED
- [ ] Ruff clean on changed files: `ruff check <files>`
- [ ] No secrets in the diff: `git diff HEAD~20 | grep -iE "api[_-]?key|token|secret" ` reviewed
- [ ] CHANGELOG.md updated (Unreleased → new version, date)

## 2. Tag & build

- [ ] `git tag vX.Y.Z && git push origin vX.Y.Z`
- [ ] GitHub Actions `release.yml` run green (~25–40 min)
- [ ] Release page shows: `JARVIS-Setup-vX.Y.Z.exe` + `JARVIS-portable-vX.Y.Z.zip` + `SHA256SUMS.txt`

## 3. Hardware verification (first install of the tag)

- [ ] `docs/HARDWARE_CHECKLIST.md` completed on the target machine
- [ ] Installer: per-user install, no admin prompt, Start-menu entry
- [ ] Portable zip runs from a path with spaces
- [ ] `certutil -hashfile` matches SHA256SUMS.txt
- [ ] Uninstall works; config/log deletion offered, not forced
- [ ] Auto-update: an older install detects the new release

## 4. Announce (only after 1–3 are green)

- [ ] Release notes mention the SmartScreen "Unknown publisher" path
      (until the build is code-signed)
- [ ] Demo video / GIFs refreshed if behavior changed
- [ ] Benchmarks table updated with measured numbers only

## Versioning (SemVer)

- MAJOR: breaking changes to settings.toml schema, tool names, or API
- MINOR: new features, new tools, new integrations
- PATCH: bug fixes, doc fixes, perf improvements
- Pre-1.0 (`0.x.y`): anything may change; the changelog still records it.
