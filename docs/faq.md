# FAQ / Troubleshooting

## Does it work on Windows yet?

Not verified. The code is complete and tested on Linux; `v1.0.0` is the
first release that will be installed and tested on real Windows hardware.
We won't claim otherwise.

## Why does it ask me "haan ya nahi" so often?

That's the autonomy dial (`safety.autonomy_level` in settings.toml):

- `0` — asks about everything
- `1` — read-only actions run free, rest ask (default)
- `2` — reversible actions also run free
- `3` — destructive actions run free too (SYSTEM tools always ask)

## It said "Ho gaya" but nothing happened?

That would be a bug — report it. Tools that can't verify their result are
required to say "confirm nahi kar paaya" instead (Phase 5 postcondition
rule). If a tool lied, we want to know.

## SmartScreen says "Unknown publisher"?

Expected for v1: the installer is unsigned (certificates cost money).
More info → Run anyway. Signing is planned once there's revenue.

## `jarvis --safe` — what does it do?

Safe mode: only the local reflex layer and READ tools run. Anything that
changes state is denied outright — useful for demos and debugging.

## Offline mode?

`privacy.offline = true` in settings.toml: no network calls at all —
cloud STT/TTS/LLM off, Google integrations fall back to fakes, and
network tools are denied at the policy gate.

## Where do crash reports go?

`~/.jarvis/crashes/` on your machine. They're never uploaded unless you
explicitly set `privacy.crash_upload = true` **and** a `crash_upload_url`.

## Can it clone someone else's voice?

No. XTTS custom voices require explicit `voice_custom_consent=true` and
the voice file must live inside a JARVIS-owned directory — your voice,
your consent.

## I found a security issue

See `SECURITY.md` (repo root) for responsible disclosure. Please don't
open a public issue for vulnerabilities.

## The wake word triggers on TV voices?

Known limitation (Phase 9 moonshot: speaker verification). Mitigations:
raise the wake-word threshold (`docs/WAKEWORD_TEST.md`), or use
push-to-talk.
