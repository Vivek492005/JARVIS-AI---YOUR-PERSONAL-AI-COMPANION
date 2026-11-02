# JARVIS — docs

JARVIS is a voice+text AI companion for Windows: talk to it (Hindi, English,
or Hinglish), and it acts on your computer through a safety-gated tool
system — confirming before anything destructive, logging everything locally.

!!! warning "Project status"
    JARVIS is in late development (`v0.9.0`). The code is fully tested on
    Linux; the first real Windows verification happens with `v1.0.0`.
    Anything marked "needs hardware" below is genuinely untested — we say
    so explicitly instead of implying it works.

## Start here

- **[Quickstart](quickstart.md)** — install and first command in 5 minutes
  (on the v1.0.0 installer; until then, from source).
- **[Architecture](architecture.md)** — how the pieces fit together.
- **[Security model](THREAT_MODEL.md)** — the part we're proudest of:
  risk tiers, the policy gate, and why a prompt injection can't delete
  your files.
- **[FAQ](faq.md)** — the questions everyone asks.

## For contributors

- `CONTRIBUTING.md` (repo root), `AUDIT_2026-11.md`, `DECISION_*.md`
  (architecture decision records).
