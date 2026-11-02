# Skill gallery — Task 8.8

> v1.0 ships the bundled set below. Community submissions open after v1.0;
> accepted skills will be hash-pinned and sandboxed (Level B minimum).

## Bundled skills (`skills/`)

| Skill | What it does |
|---|---|
| `download-media` | download video/audio via yt-dlp |
| `gesture-confirm` | thumbs-up/down confirmation channel (optional plugin) |
| `keyboard-mouse` | type text, hotkeys, clicks |
| `manage-notes` | save/search notes |
| `open-application` | launch apps by allowlisted name |
| `open-website` | open URLs in the default browser |
| `run-command` | read-only shell lookups |
| `run-powershell` | read-only PowerShell lookups |
| `system-control` | volume/brightness/wifi, lock, recycle bin |
| `web-search` | web search (results treated as untrusted data) |

## Optional plugins

`gesture-confirm` (above) is the reference optional plugin: the camera
opens only for the 15 s confirmation window and frames are never saved.

## Submitting a skill (post-v1.0)

1. Follow `docs/skills-guide.md` (manifest + risk tiers + tests).
2. Open a PR with the `new-skill` label.
3. A maintainer reviews permissions; merged skills are hash-pinned.

See also: `.github/ISSUE_TEMPLATE/good-first-issue.md`.
