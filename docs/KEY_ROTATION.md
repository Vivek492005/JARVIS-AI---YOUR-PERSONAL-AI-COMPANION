# Key Rotation — JARVIS

How API keys are stored, and how to rotate one when it leaks, expires,
or an employee/PC changes hands. **Never paste a key into chat, a file,
a screenshot, or a commit** — the 2026-10-19 incident is why this doc exists.

## Where keys live (priority order)

1. **Environment variable** (`HUGGINGFACE_API_KEY`, `DEEPSEEK_API_KEY`,
   `RUMIK_API_KEY`) — highest priority, best for CI/machines you manage.
2. **OS keyring** (Windows Credential Manager via the `keyring` package)
   — best for a personal PC. Managed with:
   - `python -m access_os.secrets store HUGGINGFACE_API_KEY` (prompts,
     hidden input — the value never touches the terminal history)
   - `python -m access_os.secrets status` (shows *where* each key is set,
     never the value)
   - `python -m access_os.secrets delete HUGGINGFACE_API_KEY`
3. **`.env` file** (repo root, git-ignored) — fallback. See `env.example`.

Keys are **never** in `settings.toml`, the audit log (`audit/*.jsonl`
redacts them — Task 1.7), or application logs (the `SecretRedactingFilter`
scrubs values — Task 1.9). `python -m access_os.config show` prints
`***set***`, never the value.

## Rotation procedure (any provider)

1. **Create the new key** at the provider:
   - Hugging Face: https://huggingface.co/settings/tokens → *Create new token*
     (fine-grained, least privilege)
   - DeepSeek: https://platform.deepseek.com/api_keys
   - Rumik: Rumik dashboard → API keys
2. **Store the new key** (pick one home — don't split a key across homes):
   - Keyring: `python -m access_os.secrets store <NAME>`
   - or `.env`: `<NAME>=<new key>`
3. **Restart JARVIS** so the new key loads (`get_settings()` is cached per
   process; the agent reads keys at startup).
4. **Verify**: `python -m access_os.secrets status` → the key shows as set;
   trigger one AI request (e.g. ask JARVIS a question) and confirm it
   answers instead of falling back to the local engine.
5. **Revoke the old key** at the provider dashboard (step 1 links). Do this
   *after* step 4 succeeds — never before.
6. If the old key was committed, screenshotted, or pasted anywhere:
   treat it as compromised — revoke first, rotate second, and check the
   provider's usage dashboard for unexpected calls.

## If a key leaks

1. Revoke it at the provider **immediately** (links above).
2. Rotate per the procedure above.
3. Check `audit/` for unusual tool activity around the leak window:
   `python -m access_os.audit search <provider>` / `tail --decision deny`.
4. Do **not** "rotate" by editing history — a revoked key is dead; rewriting
   git history doesn't un-expose it.

## Notes

- The `keyring` package is optional. Without it, `store` prints a hint to
  use `.env`, and everything else works unchanged.
- On a shared/family PC, prefer the keyring over `.env` — `.env` is a
  plaintext file; the keyring is OS-encrypted.
- Service/CI machines: use real environment variables, never `.env`.
