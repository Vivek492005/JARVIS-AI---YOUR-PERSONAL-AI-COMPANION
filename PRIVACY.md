# Privacy — JARVIS

What data leaves this machine, to whom, and when. Nothing below is
optional-to-know: if JARVIS sends it, it's in this table.

## Egress table

| Data | Destination | When | Toggle |
|---|---|---|---|
| Mic audio (your voice) | Google Speech Recognition (`recognize_google`) | Every voice command, after the wake word (if required) | `privacy.allow_google_stt` |
| Chat text (what you said/typed) | Hugging Face router → Qwen 2.5 72B | Every AI request (primary) | `privacy.allow_huggingface` |
| Chat text | DeepSeek API | When the HF client fails (backup) | `privacy.allow_deepseek` |
| Spoken-response text | Rumik AI TTS API | Every spoken reply (primary voice) | `privacy.allow_rumik_tts` |
| Spoken-response text | Microsoft Neural voice (edge-tts) | When Rumik fails (fallback voice) | — (off under Privacy Mode) |
| Search query | google.com (opened in *your* browser) | `web_search` tool | — (user-initiated) |
| Video URL / search | YouTube etc. via yt-dlp | `download_media` tool | — (user-initiated) |
| Opened URLs | Your browser | `open_website` tool | — (user-initiated, http/https only) |

**Never leaves the machine:** notes file, screenshots, audit log
(`audit/*.jsonl`, git-ignored), settings, mic audio recordings (none are
written to disk — Task 1.6.4), API keys (env/keyring only, redacted in
audit + logs — Tasks 1.7/1.9).

## Privacy Mode

One switch, total local operation:

- **Mic:** off entirely — no capture, no wake-word scanning (Task 1.6.3).
- **Brain:** cloud LLM clients are not created and not called; every
  request runs through the local fallback engine (Task 1.10).
- **Voice:** TTS uses the offline `pyttsx3` engine only — no Rumik, no
  neural voices.

Toggle it in the GUI (🔒 Privacy button), or set
`privacy_mode = true` under `[privacy]` in `settings.toml`. The GUI
toggle also persists the setting.

## Per-provider toggles

In `settings.toml` under `[privacy]` (or env `PRIVACY__ALLOW_HUGGINGFACE=false`):

- `allow_huggingface = false` → the primary client is never created.
- `allow_deepseek = false` → no DeepSeek fallback.
- `allow_rumik_tts = false` → TTS skips Rumik, tries neural, then offline.
- `allow_google_stt = false` → voice input pauses with a warning
  (no local STT engine ships yet — contributions welcome).

Privacy Mode overrides all four.

## Notes for the cautious

- Voice audio goes to Google's speech API by design (that's what
  `recognize_google` is). If that bothers you: Privacy Mode, or type
  instead of speaking.
- The LLM providers see your prompt text — that's how hosted inference
  works. Don't dictate passwords, OTPs, or private documents to JARVIS;
  the policy engine can't un-send a prompt.
- Screenshots stay on disk in `screenshots/` — they are never uploaded
  by JARVIS itself.
