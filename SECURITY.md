# Security Policy (Task 0.5)

## Supported versions

| Version | Supported |
|---------|-----------|
| v0.2.x (alpha) | ✅ security fixes on a best-effort basis |
| < v0.2 | ❌ |

JARVIS is **alpha software** that controls your keyboard, mouse, microphone
and shell. Treat every release accordingly: run it on a machine you can
afford to reinstall, and keep backups.

## Reporting a vulnerability

**Do not open a public issue.** Email the maintainer privately
(see the repo profile) with:

1. What you did (steps to reproduce)
2. What you expected vs what happened
3. The JARVIS version / commit and your Windows build

We aim to acknowledge within 7 days. If the report involves a leaked
credential, **rotate the key first** — removing it from git history does
not make it safe.

## What we promise

- Tool executions go through the policy gate (`access_os/command_policy.py`
  + Phase 1 tool registry); destructive/system actions ask first.
- Secrets are never written to logs, `settings.toml`, or the audit trail —
  they live in `.env` / the OS credential store only.
- `gitleaks` runs in CI and as a pre-commit hook on every commit.

## Known limits (see also `docs/THREAT_MODEL.md`)

- Prompt injection is an industry-wide unsolved problem. JARVIS *contains*
  it (taint tracking, untrusted-data tagging, confirm-before-act) but cannot
  *prevent* a sufficiently clever page from confusing the model.
- The local heuristic fallback and the voice regex engine act on fixed
  phrases; a misheard phrase can still trigger an unintended harmless action.
