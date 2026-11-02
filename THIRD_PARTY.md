# Third-party licenses — Task 8.8

JARVIS itself is MIT licensed (see `LICENSE`). This file lists the
runtime dependencies and their licenses, verified against PyPI metadata
on 2026-11-02. Regenerate the table with the same queries if dependencies
change.

| Package | License (PyPI) | Notes |
|---|---|---|
| Pillow | MIT-CMU | image handling |
| SpeechRecognition | BSD-3-Clause | Google Web Speech STT |
| edge-tts | LGPLv3 | primary neural TTS |
| fuzzywuzzy | **GPLv2** | fuzzy command matching (see note) |
| httpx | BSD-3-Clause | HTTP client (providers, Telegram, updater) |
| mediapipe | Apache-2.0 | gesture plugin (optional) |
| numpy | BSD-3-Clause | audio/vision arrays |
| openai | Apache-2.0 | OpenAI-compatible provider client |
| opencv-python | Apache-2.0 | camera input (optional) |
| psutil | BSD-3-Clause | system info |
| pyautogui | BSD | mouse/keyboard control |
| pydantic | MIT | config + tool schemas |
| pydantic-settings | MIT | settings management |
| pyperclip | BSD | clipboard |
| python-dotenv | BSD-3-Clause | .env loading |
| pyttsx3 | MPL-2.0 | offline TTS fallback |
| yt-dlp | Unlicense | media download tool |

## GPL note (fuzzywuzzy)

`fuzzywuzzy` is GPLv2 — the only copyleft license in the runtime set. It is
used for fuzzy command matching only. If copyleft is a concern for your
distribution, `rapidfuzz` (MIT) is a near drop-in replacement; switching is
tracked as a post-v1.0 packaging task. This is not legal advice — for
commercial distribution questions, consult a lawyer (see
`docs/LEGAL_NOTES.md`).

## Optional / dev dependencies

`requirements-optional.txt` (XTTS, faster-whisper, etc.) and
`requirements-dev.txt` (pytest, mkdocs, …) carry their own licenses;
check before bundling them into a release.
