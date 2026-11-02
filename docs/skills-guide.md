# Skills guide

Skills are JARVIS's unit of capability: a folder with a manifest, prompts,
and optionally code. The 9 bundled ("dogfood") skills live in `skills/`;
the gesture-confirm skill is the reference example of an optional plugin.

## Using skills

```bash
python -m jarvis skill list              # what's installed
python -m jarvis skill enable <name>     # turn one on
python -m jarvis skill disable <name>    # turn one off
```

The control center (`/hud` → control page) shows each skill's permissions.

## Writing a skill

```
skills/my-skill/
  SKILL.md        # name, description, when to use, examples (required)
  prompts/        # extra prompt snippets (optional)
  tools.py        # ToolSpec definitions (optional)
  manifest.toml   # permissions: which risk tiers it may use (required)
```

Rules:

1. **Every new tool gets a risk tier.** When in doubt, pick the higher one.
2. **No permanent-delete tools.** Destructive = trash/recycle only.
3. **Third-party skills run sandboxed** (Level B minimum) — see the Phase 5
   sandbox doc.
4. **Postconditions must be honest:** if your tool can't verify it did the
   thing, it must say "confirm nahi kar paaya" — never "Ho gaya".
5. Add tests. `tests/unit/test_phase4_skills.py` shows the pattern.

## Community gallery

Planned: a skill gallery with hash-pinned community skills
(`docs/SKILL_GALLERY.md`). Not live yet — v1.0 ships the bundled set only.
