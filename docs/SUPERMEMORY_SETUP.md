# Supermemory Setup — JARVIS Whole-Brain Memory (Windows)

JARVIS can use [Supermemory](https://supermemory.ai) as its semantic memory
brain: memories are recalled by *meaning* (not keywords), important facts are
captured automatically from conversation, and a user profile builds up over
time.

**You don't have to do any of this.** If the Supermemory server isn't running,
JARVIS silently falls back to its built-in local memory (SQLite) — everything
keeps working exactly as before. This guide is for enabling the full
semantic brain.

## 1. Install Node.js 18+

Download from https://nodejs.org and install the LTS version. Verify:

```powershell
node --version   # v18 or higher
```

## 2. Install the Supermemory server

```powershell
npx supermemory local install
```

This downloads one self-contained binary — no Docker, no database to configure.
Everything stays on your machine.

## 3. Start the server

```powershell
npx supermemory local start
```

Default port is **6767**. On first boot it prints a local API key — copy it;
you'll need it below. Keep this terminal open, or move to step 4 for autostart.

Verify it's alive:

```powershell
curl http://127.0.0.1:6767/ns/jarvis/profile -X POST -H "Content-Type: application/json" -d "{}"
```

(Any JSON response, even `{}`, means the server is up.)

## 4. Autostart on login (Task Scheduler)

1. Open **Task Scheduler** → *Create Task*.
2. **General**: name `Supermemory Server`, tick *Run whether user is logged on or not* (optional).
3. **Triggers**: *New…* → *At log on* → your user → OK.
4. **Actions**: *New…* → *Start a program*:
   - Program: `npx.cmd`
   - Arguments: `supermemory local start`
   - Start in: `%USERPROFILE%`
5. OK → enter your password if prompted.

## 5. Configure JARVIS

Set these environment variables (System Properties → Environment Variables,
or per-session in PowerShell):

| Variable | Purpose | Default |
|---|---|---|
| `JARVIS_SUPERMEMORY_URL` | Server URL | `http://127.0.0.1:6767` |
| `JARVIS_SUPERMEMORY_API_KEY` | Key printed on first boot | (empty) |
| `JARVIS_SUPERMEMORY_NAMESPACE` | Memory namespace | `jarvis` |
| `JARVIS_SEMANTIC_MEMORY` | `0` = kill-switch: pure-local mode | `1` |

Example (PowerShell, current session):

```powershell
$env:JARVIS_SUPERMEMORY_URL = "http://127.0.0.1:6767"
$env:JARVIS_SUPERMEMORY_API_KEY = "sm_..."
```

## 6. Verify

```powershell
python -m jarvis memory status
```

Expected:

```
semantic backend : up (http://127.0.0.1:6767)
local backend    : up
last backend used: sqlite
semantic enabled : True (JARVIS_SEMANTIC_MEMORY env)
```

Then in a JARVIS chat:

- Say `yaad rakhna meri bike red hai` → `Yaad rakh liya…`
- Later ask `meri bike ka color kya hai?` → JARVIS recalls it (semantic search, no exact words needed).

## How it works (short version)

- **Recall**: every message searches Supermemory; the best matches are injected
  into the prompt as *"Relevant memories"*.
- **Capture**: durable facts ("my X is Y", "I like…", "mera naam…", corrections)
  are saved automatically after each turn. Sensitive data (passwords, card
  numbers, OTPs) is blocked at the gate.
- **Commands**: `yaad rakhna` / `bhool ja` / `tumhe kya yaad hai` /
  `memory export` work as before — now backed by semantic search.
- **Profile**: a user profile syncs periodically and personalizes replies.
- **Fail-open**: server down → SQLite takes over silently. Nothing ever breaks.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `semantic backend : down` | Is `supermemory local start` running? Check the port. |
| Memories not recalled | Wait ~30s after adding — ingestion is async unless `dreaming: instant`. |
| Want it off temporarily | `JARVIS_SEMANTIC_MEMORY=0` — pure local mode, no server needed. |
| Start over | `jarvis memory wipe` (asks for confirmation), or delete the namespace server-side. |

## Privacy notes

- Self-hosted = your memories never leave your machine.
- Privacy Mode still works: semantic calls are localhost-only there.
- Web/file/clipboard content can never write to memory (poisoning defense) —
  only your own words (or your explicit confirmations) are stored.
