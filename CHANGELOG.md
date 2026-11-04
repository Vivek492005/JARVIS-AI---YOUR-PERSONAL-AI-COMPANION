# Changelog

All notable changes to JARVIS are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

> **Status honesty:** tags `v0.2.0`–`v0.9.0` are *code-complete* milestones —
> every behavior is covered by automated tests on Linux, but none has been
> verified on real Windows hardware yet. `v1.0.0` is reserved for the first
> release that passes the full `docs/HARDWARE_CHECKLIST.md` on a real
> machine.

## [Unreleased]

### Added
- **Phase 9 moonshot: self-improving skills (human-reviewed).** Hermes-style
  learning loop: privacy-safe signal store (redacted args, sensitive
  content withheld, no raw utterances), poisoning guard (untrusted/MCP
  content never learnable), offline proposer (`reflex_rule` /
  `prompt_snippet` / `skill_variant`), control-center proposals inbox with
  approve/reject/edit/revert, eval-gated apply (fail-closed, safety +
  injection always at 100%), versioned reversible changes, `jarvis learn`
  CLI. Never auto-applies — every change is an explicit human decision.
- **Phase 9 moonshot: signed skill marketplace.** `.jskill` packages
  (strict MANIFEST.json + hash-pinned files), pure-Python Ed25519
  sign/verify (stdlib only, libsodium-pinned vectors), trust tiers
  (self-signed / curator / reserved verified), fail-closed
  `jarvis skill install|verify`, curator key store, signed revocation
  feeds with offline cache, author tooling
  (`keygen`/`package`/`trust`/`update-revocations`), sandbox Level B+
  gate for third-party skills, audit-log entries, and
  `docs/SKILL_MARKETPLACE.md` (trust model, author guide, reviewer
  checklist). No registry server yet — distribution is files.
- Test-pyramid coverage gate: core modules (policy, lane queue, memory,
  model router) must stay ≥ 80% (`scripts/check_coverage.py`).
- Performance budget doc + profiler + CI-safe perf gate tests.
- Reliability: service watchdog with backoff, `jarvis --safe` mode
  (reflex + READ tools only), offline mode (no network, fail-closed),
  settings.toml schema migrations, local crash reports (opt-in upload).
- Packaging: portable-zip builder, SHA256SUMS generation, auto-update
  client with hash verification, static validation of the PyInstaller
  spec / Inno script / release workflow.

## [0.9.0] - 2026-11-02

### Added
- HUD, Persona & Experience (Phase 7): web HUD served by jarvisd (orb,
  transcript, action timeline, Haan/Nahi confirm cards, PWA manifest),
  persona engine (safety guard can't be overridden by persona files),
  voice identity with XTTS consent gate, 5 synthesized earcons,
  `jarvis onboard` 8-step wizard, control center API + page,
  gesture-confirm optional skill, mobile PWA (offline queue, push hooks),
  tray icon + global hotkey summon.
- UI technology decision documented: web-HUD-first for v1.0
  (`docs/DECISION_UI.md`); Tauri deferred to v1.1.

## [0.8.0] - 2026-11-02

### Added
- Integrations, MCP & Proactivity (Phase 6): MCP client (JSON-RPC over
  stdio, allowlisted servers, poisoned-output guards), JARVIS as an MCP
  server (READ/REVERSIBLE tools only, token auth), Calendar/Mail/Tasks
  (fake-by-default, opt-in Google provider), heartbeat + scheduler
  (above-READ timer actions become notifications, never silent execution),
  Telegram remote control (user allowlist, reduced remote autonomy).

## [0.7.0] - 2026-11-01

### Added
- Perception & OS control (Phase 5): UIA control-surface ladder, screen
  capture + OCR with PII redaction, VLM set-of-marks (login/CAPTCHA
  auto-handoff), browser agent (dedicated profile, SSRF deny), file
  intelligence (workspace-scoped, trash-only delete), app adapters
  (VS Code / Office / Spotify / settings), postcondition honesty rules,
  sandbox levels for third-party skills.

## [0.6.0] - 2026-11-01

### Added
- Agent brain (Phase 4): agent loop, model router with cost control,
  versioned prompts, SQLite memory with poisoning guard, 9 dogfood skills,
  250-case eval suite, approval-gated reflection, disambiguation +
  undo journal.

## [0.5.0] - 2026-11-01

### Added
- Voice pipeline (Phase 3): 16 kHz audio frames with EchoGuard, pluggable
  wake-word backends, dynamic-noise-floor VAD (Hindi + English),
  STT engine registry + bake-off harness, streaming STT/TTS, XTTS v2
  local voice engine, barge-in, dialogue FSM, input modes, latency
  budgets in `jarvis doctor`.

## [0.4.0] - 2026-11-01

### Added
- Core runtime (Phase 2): `src/jarvis` package layout, event bus, lane
  queue (serial + priority + cancel), jarvisd service/client split
  (FastAPI, per-install token, WS events), provider abstraction with
  retry + circuit breaker, 152-rule reflex layer, observability
  (JSON logs, trace ids, metrics, `jarvis doctor`).

## [0.3.0] - 2026-11-01

### Added
- Safety architecture (Phase 1): threat model, tool registry with risk
  tiers, L0–L3 policy engine, foreground guard, prompt-injection
  containment (34-case corpus), mic safety, redacted audit log,
  kill switch, rate limiter, circuit breaker, OS-keyring secrets,
  privacy egress controls.

## [0.2.0] - 2026-11-01

### Added
- Foundation (Phase 0): JARVIS identity, typed settings (secrets env-only),
  pyproject + lockfile, pre-commit + gitleaks + SECURITY.md, CI workflow,
  honest README, queue-based main loop with status reporting.

### Fixed
- A-01 (critical): local-fallback path bypassed the policy gate — now
  routes through `run_action()` like everything else.
- A-02 (high): `open_application` shell injection — `shell=True` removed,
  strict application-name allowlist.
