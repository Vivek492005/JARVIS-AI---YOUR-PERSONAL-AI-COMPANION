# JARVIS Chat UI — buddy + chat card

> **Design pivot (2026-11-04, user's call):** the primary surface is NOT a
> big chat window. It's a **small floating companion buddy** (~76px,
> bottom-right, like the ChatGPT desktop "PET" buddy). Clicking the buddy
> expands a compact chat card (~380×520). The full-page chat
> (`/hud/chat.html`) remains as an alternative view.

## The buddy (`/hud/buddy.html`)

A tiny, cute, always-visible companion anchored bottom-right:

- **Idle** — gentle bobbing, blinking eyes every ~4s, soft teal glow.
- **Hover** — happy wiggle.
- **Listening** — pulsing glow ring.
- **Thinking** — bouncy hop.
- **Speaking** — mouth opens/closes.
- **Attention** — excited bounce + orange notification dot (e.g. a Haan/Nahi
  confirm is waiting). Cleared when the chat card opens.
- **Draggable** — drag it anywhere; position persists in localStorage.
  A tap (no drag) toggles the chat card. Keyboard: Enter/Space toggles,
  Escape closes.
- `prefers-reduced-motion` disables all character animation.

Pure CSS character — no images, no CDN. State comes from live jarvisd
events via `window.JarvisBuddy.setState()` (bridged in `chat.js` `onEvent`).

## The chat card

Expands from the buddy with a springy scale animation. Compact (~380×520,
bottom-right anchored) with the full chat feature set:

- Conversation thread — user/JARVIS bubbles, timestamps, auto-scroll,
  typewriter streaming, safe markdown rendering.
- Inline Haan/Nahi confirm cards (same `/command` pipeline as the HUD).
- "Working…" indicator with collapsible tool list, collapsed into the
  message afterwards.
- Composer — auto-growing textarea, Enter to send, Shift+Enter newline,
  Send/Stop (real `POST /interrupt`), mic (Web Speech API with graceful
  fallback note).
- Message actions — copy, retry, speak.
- Conversations persist in localStorage; header shows the active chat title,
  `+` starts a new chat. (The full sidebar lives on the full-page chat.)
- Close (×) or click-outside collapses back to just the buddy.
- "Pop out" button (`⧉`) opens the buddy in a compact 430×680 popup window
  for a closer always-on-top feel.

## Opening it

```
python -m jarvis serve --http          # starts jarvisd + tray + hotkey
# then: press Ctrl+Alt+J, or tray icon → "Open chat"
```

The summon opens `http://127.0.0.1:<port>/hud/buddy.html?token=<install-token>`
in the default browser. The per-install bearer <redacted> travels as `?token=`
(same pattern as the existing HUD) and as an `Authorization` header on API
calls.

Note: a plain browser tab can't float above other windows — for the true
floating feel, use the pop-out button (compact popup window). A future
native wrapper could host `buddy.html` borderless; the page is already
transparent-background and self-contained for that.

## Full-page chat (`/hud/chat.html`)

Same conversation engine with a sidebar (conversation list, new/rename/
delete, speak-replies and high-contrast toggles). Linked from the HUD
header's **Chat** tab. The HUD orb/panel/full modes are untouched.

## Streaming: an honest note

The provider layer returns whole completions — there is **no token streaming**
server-side, so no new streaming endpoint was added (adding one would mean
re-plumbing providers → agent loop → event bus, untestable here). The chat
renders the full `SpeechStarted` text progressively instead. `onToken()` in
`chat.js` is the hook a future server streaming endpoint can call.

## Markdown rendering

`renderMarkdown()` escapes HTML **first**, then applies a limited subset:
fenced code blocks, inline code, bold/italic, `http(s)` links only, lists.
Raw model output never reaches `innerHTML`.

## Files

- `src/jarvis/hud/static/buddy.html` — buddy + chat card shell
- `src/jarvis/hud/static/buddy.css` — character + card styles
- `src/jarvis/hud/static/buddy.js` — expand/collapse, drag, pop-out,
  state bridge endpoint (`window.JarvisBuddy`)
- `src/jarvis/hud/static/chat.html` / `chat.css` / `chat.js` — full-page chat
  (also embedded by buddy.html; sidebar parts are optional/guarded)
- `src/jarvis/server/api.py` — serves all files (auth'd, allowlisted);
  `POST /interrupt` (auth'd)
- `src/jarvis/hud/static/sw.js` — app-shell cache (`jarvis-hud-v3`)
- `src/jarvis/hud/tray.py` — menu item "Open chat"
- `src/jarvis/cli.py` — `_start_summon_ui()`: tray + hotkey wired into
  `serve --http`, opening the buddy; failures only log, never break serve

## Needs a real Windows desktop to verify

- Ctrl+Alt+J summons the buddy (hotkey + tray need pystray/`keyboard` +
  a real desktop; untestable here)
- Buddy character look/feel: blink/bob/wiggle/speaking mouth on real render
- Drag smoothness, pop-out popup window behavior
- Mic button via Web Speech API (mic permission), typewriter smoothness
- PWA install + offline-queue flush on a real network drop
