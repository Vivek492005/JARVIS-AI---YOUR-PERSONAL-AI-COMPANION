# Branding & naming — Task 8.8

## The "JARVIS" name

"JARVIS" is famously the AI from Marvel's Iron Man films. This project
started as a fan-inspired build, and the name stuck during development.

**For a public release, this is a real trademark risk.** Marvel/Disney
actively protect character names in software. Options, in order of safety:

1. **Rename for v1.0** — pick an original name, keep "JARVIS-inspired" as
   a tagline. Safest, and it's *our* product then.
2. **Keep JARVIS as the internal/dev codename**, ship under a different
   public brand.
3. **Keep the name and accept the risk** — not recommended without a
   lawyer's opinion.

No decision has been made yet. This doc exists so the decision is explicit
before v1.0.0, not discovered via a takedown notice after.

*This is not legal advice. For the actual call, talk to a lawyer —
see `docs/LEGAL_NOTES.md`.*

## Current brand assets

- Name in code/config: `JARVIS` / `jarvis`
- Landing page: `index.html` (repo root, GitHub Pages)
- License: MIT (`LICENSE`)

## If we rename

Checklist: repo name, `APP_NAME` in config, installer names, docs site
title, HUD strings, PERSONA.md, release notes. The rename should land as
its own tagged release *before* v1.0.0 marketing begins.
