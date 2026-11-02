# Integrations Setup (Phase 6)

All credentials live in **env vars or the OS keyring** — never in files.
Store a secret with:

```powershell
python -m jarvis.core.secrets store TELEGRAM_BOT_TOKEN
```

(or set the env var directly). `python -m jarvis.core.secrets status`
lists *names only*, never values.

## Telegram remote control (6.5)

1. Talk to `@BotFather` on Telegram → `/newbot` → copy the token.
2. `python -m jarvis.core.secrets store TELEGRAM_BOT_TOKEN` (paste it).
3. Set `TELEGRAM_ALLOWED_USERS` to your numeric Telegram user id
   (comma-separated for more people). Get it from `@userinfobot`.
4. Start the bot from the app; it long-polls (no webhook/port needed).

Safety: only allowlisted users are answered; remote autonomy is one
level lower than configured; SYSTEM tools are **denied** remotely unless
you explicitly opt in (`remote_system_tools=True` in code — there is no
config flag on purpose).

## Google Calendar / Gmail / Tasks (6.3)

1. [Google Cloud Console](https://console.cloud.google.com/) → new
   project → enable **Calendar API**, **Gmail API**, **Tasks API**.
2. OAuth consent screen (External, test mode) → add your Gmail as test user.
3. Credentials → Create **OAuth client ID** (Desktop app) → download JSON.
4. Convert to a token (one-time, on your machine):
   ```powershell
   pip install google-auth-oauthlib
   python - <<'EOF'
   import json
   from google_auth_oauthlib.flow import InstalledAppFlow
   flow = InstalledAppFlow.from_client_secrets_file(
       "client_secret.json",
       ["https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/tasks"])
   creds = flow.run_local_server(port=0)
   print(creds.to_json())   # paste into the next step, then close this
   EOF
   ```
5. `python -m jarvis.core.secrets store GOOGLE_OAUTH_TOKEN_JSON`
   (paste the JSON), then set env `JARVIS_PIM_PROVIDER=google`.
6. **Revoke any time**: Google Account → Security → Third-party access.

Without `JARVIS_PIM_PROVIDER=google`, JARVIS uses built-in fakes —
no account is ever touched by accident.

## MCP servers (6.1)

1. Copy `mcp_servers.toml.example` → `mcp_servers.toml`, edit the paths.
2. Point `mcp_servers_toml` at it in settings (default: `./mcp_servers.toml`).
3. Run the `mcp_discover` tool (SYSTEM tier — it asks for confirmation)
   to connect and register each server's tools.
4. Review discovered tools, then downgrade individual risks with
   `risk_overrides` in the toml.

## JARVIS as MCP server (6.2)

```powershell
$env:JARVIS_MCP_TOKEN = "<long-random-string>"
python -m jarvis.integrations.mcp_server
```

Point your MCP client (Claude Desktop etc.) at this command over stdio
and pass the same token in the `initialize` params as
`{"token": "<same-string>"}`. Only READ/REVERSIBLE tools are exposed;
every call runs through the policy engine and audit log.

## Heartbeat & scheduler (6.4)

- Heartbeat runs every 30 min, quiet hours 23:00–07:00, max 20
  proactive notifications/day (all in `HeartbeatConfig`).
- Per-rule opt-in: `calendar_meeting`, `mail_vip`, `battery_low`
  (default on), `daily_brief` (default off).
- Scheduler: `scheduler_add` tool (cron / every_s / one-shot / file-watch).
  Timers **never** auto-run above-READ tools — those become a
  confirmation notification instead.
