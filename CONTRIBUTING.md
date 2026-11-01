# Contributing to JARVIS

Thanks for your interest! JARVIS is alpha software — please read this before
opening a PR.

## Ground rules

1. **Safety first.** Any PR that touches tool execution, the policy gate,
   subprocess/keyboard control, or network egress must include tests proving
   the safe behaviour (see `tests/security/`).
2. **No secrets, ever.** API keys, tokens, and credentials go in `.env`
   (local only). `gitleaks` runs in CI and pre-commit — a leak fails the build.
3. **Honest docs.** If your change alters behaviour, update `README.md`,
   `VOICE_COMMANDS.md`, and the relevant `docs/` page in the same PR.
4. **One phase at a time.** Big refactors belong to the phase that the
   [master plan](JARVIS_MASTER_PLAN.md) assigns them to.

## Development setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
pytest -m "not hardware and not live"
```

## Test tiers

| Marker | Meaning | Runs in CI |
|--------|---------|------------|
| (none) | unit test, mocked hardware | ✅ |
| `hardware` | needs camera/mic | ❌ (manual) |
| `live` | needs real network APIs | ❌ (manual) |
| `slow` | long-running | ❌ |

## Pull requests

- Keep PRs small and focused; one task-ID per PR is ideal.
- `ruff check` and `ruff format --check` must pass.
- Update `docs/` when behaviour changes.
