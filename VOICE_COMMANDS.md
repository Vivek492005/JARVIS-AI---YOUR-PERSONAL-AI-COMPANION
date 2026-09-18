# 🤖 JARVIS / JARVIS — Complete Voice Commands & AI Agent Guide

**JARVIS / JARVIS** is an intelligent, production-grade AI voice companion for Windows. Driven by **Qwen 2.5 72B Instruct (via Hugging Face Router)** and **Rumik AI Silk TTS**, it combines an autonomous function-calling LLM brain with 100+ local OS automation tools.

---

## 🧠 What's New: The Autonomous AI Agent Engine

You no longer need to memorize exact command formats! JARVIS now uses **natural language reasoning and tool calling**:
- **Multi-Lingual Intent**: Speak naturally in **English, Hindi, or Hinglish** (*"Yaar ek acha sa song download karde"*, *"Chrome kholo aur latest tech news dikhao"*).
- **Multi-Action Chaining**: Combine instructions in one go (*"Open notepad and write down today's meeting notes"*).
- **Autonomous Tool Dispatch**: Qwen 72B will autonomously choose to launch applications, search the web, download media with `yt-dlp`, write notes, simulate keystrokes, or control hardware settings.
- **Contextual Memory**: Follow-up questions and chained commands (*"Now search for that"*, *"Make it louder"*, *"Save that note"*) retain conversation history.
- **High-Definition Voice**: Speaks back with human-like **Rumik AI Silk TTS** (`muga` model).

---

## 🚀 1. Autonomous AI Commands & Tool Calling Examples

Below are practical ways to interact with the LLM Brain. Say them in **any phrasing or language**:

### 📥 Media & Song Downloads (`download_media`)
| What You Can Say (Natural Voice) | What JARVIS Does Autonomously |
|:---|:---|
| **"Download song Believer by Imagine Dragons"** | Automatically searches YouTube, extracts high-quality audio (MP3), and saves it to your `Music` folder |
| **"Download video Python in 100 seconds"** | Downloads full MP4 video to your `Downloads` folder using `yt-dlp` |
| **"Download this YouTube link [URL]"** | Direct URL download in optimal resolution |
| **"Bhai ye gana download kar de [Song Name]"** | Multilingual Hindi/Hinglish intent parsing into download action |

### 📝 Notes & Smart Dictation (`manage_notes` & `keyboard_mouse_action`)
| What You Can Say (Natural Voice) | What JARVIS Does Autonomously |
|:---|:---|
| **"Note that buy milk and eggs after work"** | Saves a timestamped note to `notes.txt` |
| **"Take a note: project deadline is Friday 5 PM"** | Appends entry to your notes |
| **"Read my notes"** / **"What are my latest notes?"** | Reads aloud your recent saved notes via Rumik voice |
| **"Clear all my notes"** | Erases notes file cleanly |
| **"Open notepad and write Welcome to JARVIS AI"** | Launches Notepad and automatically types text via simulated keystrokes |

### 🔍 Live Web & Real-Time Research (`web_search` & `open_website`)
| What You Can Say (Natural Voice) | What JARVIS Does Autonomously |
|:---|:---|
| **"Search Google for latest James Webb space discoveries"** | Performs Google search for the query |
| **"What's the weather like in Mumbai today?"** | Opens live weather forecast |
| **"Open github and search for AI assistant repositories"** | Opens GitHub search page |
| **"Take me to OpenAI / Hugging Face / DeepSeek"** | Automatically resolves URL and opens browser |

### 💻 System & Hardware Control (`system_control`)
| What You Can Say (Natural Voice) | What JARVIS Does Autonomously |
|:---|:---|
| **"Take a screenshot for me"** | Captures active display and saves PNG in `screenshots/` |
| **"Lock my computer"** / **"Lock workstation"** | Instantly secures Windows desktop |
| **"Empty the recycle bin"** | Cleans out deleted items without opening explorer |
| **"What's my battery percentage?"** | Reports power state and percentage aloud |
| **"Turn up the volume"** / **"Make it louder"** / **"Mute sound"** | Adjusts Windows master volume |

### 💬 General Reasoning & Conversational QA
| What You Can Say (Natural Voice) | What JARVIS Does Autonomously |
|:---|:---|
| **"Explain quantum computing in two simple sentences"** | Qwen 72B generates a concise, spoken explanation |
| **"Tell me a clever programming joke"** | Shares a programming pun via Rumik TTS |
| **"Calculate 45 times 18 plus 250"** | Direct arithmetic reasoning and spoken result |

---

## 🎙️ Dual-Input Mode: Voice & Companion Card

1. **Microphone Capture:** Speak normally into your mic. Wake word *"JARVIS"* or *"JARVIS"* is optional.
2. **Text Prompt Bar:** Click the entry box on the floating companion card, type your prompt, and press `Enter` or click `➔`.
3. **Mute Toggle:** Click `🎤 Mic On` on the companion card to pause voice listening when needed.

---

## 🌐 1. Web Portals & Social Media (25+ commands)

| Voice Command | Action |
|:---|:---|
| **"Open YouTube"** / **"YouTube"** | Opens YouTube |
| **"Open LinkedIn"** / **"LinkedIn"** | Opens LinkedIn |
| **"Open Gmail"** / **"Check email"** | Opens Gmail |
| **"Open GitHub"** / **"GitHub"** | Opens GitHub |
| **"Open Google"** | Opens Google homepage |
| **"Open WhatsApp"** / **"WhatsApp web"** | Opens WhatsApp Web |
| **"Open Twitter"** / **"Open X"** | Opens Twitter/X |
| **"Open Instagram"** | Opens Instagram |
| **"Open Facebook"** | Opens Facebook |
| **"Open Reddit"** | Opens Reddit |
| **"Open Netflix"** | Opens Netflix |
| **"Open Spotify"** | Opens Spotify web player |
| **"Open Amazon"** | Opens Amazon |
| **"Open Stack Overflow"** | Opens Stack Overflow |
| **"Open Google Maps"** / **"Maps"** | Opens Google Maps |
| **"Open Google Drive"** / **"Drive"** | Opens Google Drive |
| **"Open Google Docs"** / **"Docs"** | Opens Google Docs |
| **"Open Google Calendar"** / **"Calendar"** | Opens Google Calendar |
| **"Open News"** | Opens Google News |
| **"Open Wikipedia"** | Opens Wikipedia |
| **"Open LeetCode"** | Opens LeetCode |
| **"Open Discord"** | Opens Discord |
| **"Open Medium"** | Opens Medium |
| **"Open Pinterest"** | Opens Pinterest |
| **"Open Canva"** | Opens Canva |

---

## 🎬 2. YouTube Commands (25+ commands)

### 🔍 Search & Play
| Voice Command | Action |
|:---|:---|
| **"Play [song/video name] on YouTube"** | Searches & opens video on YouTube |
| **"Play [name] in YouTube"** | Same — searches YouTube for query |
| **"YouTube search [query]"** | Opens YouTube search results |
| **"Search YouTube for [query]"** | Opens YouTube search results |

### ⏯️ Playback Controls (keyboard shortcuts)
| Voice Command | Action |
|:---|:---|
| **"Pause YouTube"** / **"Pause video"** | Pauses/Resumes video (`K`) |
| **"Resume"** / **"Resume video"** | Resumes paused playback |
| **"Mute YouTube"** / **"Unmute YouTube"** | Toggles audio mute (`M`) |
| **"YouTube fullscreen"** / **"Fullscreen"** | Toggles fullscreen mode (`F`) |
| **"YouTube theater mode"** / **"Theater mode"** | Toggles theater/cinema mode (`T`) |
| **"YouTube miniplayer"** | Toggles mini player (`I`) |
| **"YouTube captions"** / **"Subtitles"** | Toggles captions/subtitles (`C`) |

### ⏩ Navigation
| Voice Command | Action |
|:---|:---|
| **"Skip 10 seconds"** / **"YouTube skip 10 seconds"** | Skips forward 10 seconds (`L`) |
| **"Rewind 10 seconds"** / **"YouTube rewind 10 seconds"** | Rewinds 10 seconds (`J`) |
| **"Next video"** / **"Next track"** | Presses Shift+N (next video) |
| **"Previous video"** / **"Previous track"** | Presses Shift+P (previous video) |

### ⚡ Playback Speed
| Voice Command | Action |
|:---|:---|
| **"YouTube speed up"** | Increases playback speed (`>`) |
| **"YouTube slow down"** / **"Slow down video"** | Decreases playback speed (`<`) |

### 📚 YouTube Pages
| Voice Command | Action |
|:---|:---|
| **"YouTube subscriptions"** | Opens YouTube Subscriptions feed |
| **"YouTube history"** | Opens YouTube Watch History |
| **"YouTube shorts"** | Opens YouTube Shorts feed |
| **"YouTube trending"** | Opens YouTube Trending page |
| **"YouTube liked videos"** | Opens Your Liked Videos playlist |

### ⬇️ Downloads (saved to `~/Downloads`)
| Voice Command | Action |
|:---|:---|
| **"Download this video"** / **"Download current video"** | Downloads the YouTube video from clipboard URL |
| **"Download [song name] from YouTube"** | Searches & downloads that video |
| **"Download audio of [song name]"** | Downloads MP3 audio track |
| **"Download this mp3"** / **"Download this audio"** | Downloads current video as MP3 audio |

> 💡 **Tip:** For downloads, copy the YouTube URL first (`Ctrl+L`, `Ctrl+C`) or say the song name directly.

---

## 🔊 3. Volume & Audio Control (13 commands)

| Voice Command | Action |
|:---|:---|
| **"Volume up"** / **"Increase volume"** / **"Louder"** | Increases volume by 5 steps |
| **"Volume down"** / **"Decrease volume"** / **"Softer"** | Decreases volume by 5 steps |
| **"Volume max"** / **"Maximum volume"** | Sets volume to maximum |
| **"Volume min"** / **"Minimum volume"** | Sets volume to minimum |
| **"Mute"** / **"Unmute"** / **"Toggle mute"** | Toggles Windows audio mute |
| **"Speak louder"** | Increases JARVIS voice volume |
| **"Speak softer"** | Decreases JARVIS voice volume |
| **"Speak faster"** / **"Talk faster"** | Increases JARVIS speech rate |
| **"Speak slower"** / **"Talk slower"** | Decreases JARVIS speech rate |
| **"Use female voice"** | Switches to `en-IN-NeerjaNeural` (Indian female) |
| **"Use male voice"** | Switches to `en-IN-PrabhatNeural` (Indian male) |
| **"Use American voice"** | Switches to `en-US-AvaNeural` (US English) |
| **"Use human voice"** / **"Use neural voice"** | Re-enables neural TTS |
| **"Use robotic voice"** / **"Offline voice"** | Switches to offline pyttsx3 voice |

---

## 💻 4. Windows Applications (16 commands)

| Voice Command | Action |
|:---|:---|
| **"Open Notepad"** | Launches Notepad |
| **"Open Calculator"** | Launches Calculator |
| **"Open Paint"** | Launches MS Paint |
| **"Open File Explorer"** / **"Open files"** | Opens Windows Explorer |
| **"Open Command Prompt"** / **"Open terminal"** | Launches CMD |
| **"Open PowerShell"** | Launches PowerShell |
| **"Open Task Manager"** | Launches Task Manager |
| **"Open Settings"** | Opens Windows Settings |
| **"Open Control Panel"** | Opens Control Panel |
| **"Open Chrome"** | Launches Google Chrome |
| **"Open Edge"** | Launches Microsoft Edge |
| **"Open VS Code"** / **"Open Code"** | Launches VS Code |
| **"Open Word"** | Launches Microsoft Word |
| **"Open Excel"** | Launches Microsoft Excel |
| **"Open PowerPoint"** | Launches Microsoft PowerPoint |
| **"Close window"** / **"Close app"** | Closes active window (`Alt+F4`) |

---

## 🖥️ 5. Desktop & Multitasking (10 commands)

| Voice Command | Action |
|:---|:---|
| **"Minimize"** / **"Minimize window"** | Minimizes current window |
| **"Maximize"** / **"Maximize window"** | Maximizes current window |
| **"Show desktop"** / **"Minimize all"** | Shows desktop (`Win+D`) |
| **"Switch window"** / **"Switch app"** | Alt+Tab app switcher |
| **"Task view"** | Opens Win+Tab task view |
| **"Lock computer"** / **"Lock PC"** | Locks Windows workstation |
| **"Take a screenshot"** / **"Screenshot"** | Saves screenshot to `screenshots/` |
| **"Open Action Center"** / **"Notifications"** | Opens notifications panel (`Win+A`) |
| **"Open Clipboard"** / **"Clipboard history"** | Opens clipboard history (`Win+V`) |
| **"Empty recycle bin"** | Empties the Recycle Bin |

---

## 🌍 6. Browser Navigation & Tabs (16 commands)

| Voice Command | Action |
|:---|:---|
| **"New tab"** | Opens new tab (`Ctrl+T`) |
| **"Close tab"** | Closes current tab (`Ctrl+W`) |
| **"Reopen tab"** / **"Undo close tab"** | Reopens last tab (`Ctrl+Shift+T`) |
| **"Next tab"** | Switches to next tab (`Ctrl+PageDown`) |
| **"Previous tab"** | Switches to previous tab (`Ctrl+PageUp`) |
| **"Refresh page"** / **"Reload"** | Refreshes page (`Ctrl+R`) |
| **"Bookmark page"** | Bookmarks page (`Ctrl+D`) |
| **"Open history"** | Opens browser history (`Ctrl+H`) |
| **"Open downloads"** | Opens downloads panel (`Ctrl+J`) |
| **"Open incognito"** / **"Private window"** | Opens incognito window (`Ctrl+Shift+N`) |
| **"Zoom in"** | Zooms in (`Ctrl++`) |
| **"Zoom out"** | Zooms out (`Ctrl+-`) |
| **"Reset zoom"** | Resets zoom (`Ctrl+0`) |
| **"Scroll down"** / **"Page down"** | Scrolls down |
| **"Scroll up"** / **"Page up"** | Scrolls up |
| **"Scroll to top"** / **"Scroll to bottom"** | Jumps to top/bottom |

---

## ⌨️ 7. Typing & Text Editing (15 commands)

| Voice Command | Action |
|:---|:---|
| **"Type [your text]"** | Types words at cursor position |
| **"Select all"** | Selects all text (`Ctrl+A`) |
| **"Copy"** / **"Copy that"** | Copies selection (`Ctrl+C`) |
| **"Paste"** / **"Paste that"** | Pastes from clipboard (`Ctrl+V`) |
| **"Cut"** / **"Cut that"** | Cuts selection (`Ctrl+X`) |
| **"Undo"** / **"Undo that"** | Undo action (`Ctrl+Z`) |
| **"Redo"** / **"Redo that"** | Redo action (`Ctrl+Y`) |
| **"Save file"** / **"Save"** | Saves file (`Ctrl+S`) |
| **"Find"** / **"Find in page"** | Opens find box (`Ctrl+F`) |
| **"Press enter"** / **"Enter"** | Presses Enter key |
| **"Press space"** / **"Space"** | Presses Spacebar |
| **"Press tab"** / **"Tab"** | Presses Tab key |
| **"Press backspace"** / **"Backspace"** | Presses Backspace |
| **"Press escape"** / **"Escape"** | Presses Escape |
| **"Press delete"** / **"Delete"** | Presses Delete key |

---

## 🔍 8. Web Search & Quick Info (10 commands)

| Voice Command | Action |
|:---|:---|
| **"Search for [query]"** / **"Google [query]"** | Google search |
| **"Wikipedia [topic]"** / **"Wiki [topic]"** | Wikipedia search |
| **"What time is it?"** / **"Current time"** | Announces current time |
| **"What is the date?"** / **"Today's date"** | Announces full date |
| **"What day is today?"** | Announces day of the week |
| **"Weather in [city]"** | Opens weather for that city |
| **"What is the weather?"** | Opens local weather |
| **"Define [word]"** / **"Meaning of [word]"** | Opens word definition |
| **"Speed test"** | Opens Speedtest.net |
| **"What is my IP?"** | Opens IP address checker |

---

## 🧮 9. Math & Utilities (9 commands)

| Voice Command | Action |
|:---|:---|
| **"Calculate [expression]"** (e.g., *"Calculate 45 × 12"*) | Evaluates math expression |
| **"What is [expression]"** | Answers basic math |
| **"Tell me a joke"** / **"Make me laugh"** | Tells a funny joke |
| **"Flip a coin"** | Random Heads or Tails |
| **"Roll a dice"** | Random 1–6 dice roll |
| **"Take a note [content]"** | Saves timestamped note to `notes.txt` |
| **"Read my notes"** | Reads back your saved notes |
| **"Clear notes"** | Clears `notes.txt` |
| **"Battery status"** / **"Battery level"** | Checks battery % and charging state |

---

## 🤖 10. AI Tools Suite (11 commands)

### Open AI Portals
| Voice Command | Action |
|:---|:---|
| **"Open ChatGPT"** | Opens ChatGPT |
| **"Open Claude"** / **"Claude AI"** | Opens Claude AI |
| **"Open Copilot"** / **"Microsoft Copilot"** | Opens Microsoft Copilot |
| **"Open Perplexity"** / **"Perplexity AI"** | Opens Perplexity AI |
| **"Open Gemini"** / **"Open Google Gemini"** | Opens Google Gemini |

### Query AI with Voice
| Voice Command | Action |
|:---|:---|
| **"Ask ChatGPT [your prompt]"** | Opens ChatGPT with your question pre-filled |
| **"Ask Perplexity [query]"** | Opens Perplexity with search query |
| **"Ask Copilot [query]"** | Opens Copilot with your prompt |
| **"Ask Claude [query]"** | Opens Claude (copies prompt to clipboard) |

### Smart AI Actions
| Voice Command | Action |
|:---|:---|
| **"Summarize this with AI"** / **"AI summarize"** | Copies selected text → sends to Perplexity for summary |
| **"Fix this code with AI"** / **"Debug this code with AI"** | Copies selected code → sends to AI for analysis |

> 💡 **Tip:** Highlight/select text on screen first, then say the AI command to process it.

---

## 📂 11. Smart File Locator (1 command, multiple patterns)

| Voice Command | Action |
|:---|:---|
| **"Where is [filename]"** | Searches for file across common folders |
| **"Find file [filename]"** | Searches for file and opens Explorer |
| **"Locate file [filename]"** | Same as above |
| **"Where is [filename] in C drive"** | Limits search to C:\ |
| **"Where is [filename] in downloads"** | Limits search to Downloads folder |
| **"Find [filename] in [folder name]"** | Targeted search by folder hint |

> ⚡ Search is capped at **5 seconds** to keep JARVIS responsive. It searches: Desktop, Downloads, Documents, Pictures, Music, Videos, and common project folders.

---

## 💬 12. Personality & Conversation (14 commands)

| Voice Command | Action |
|:---|:---|
| **"Are you there?"** / **"JARVIS are you there?"** | Confirms JARVIS is online |
| **"Who are you?"** / **"What is your name?"** | JARVIS introduces itself |
| **"Good morning"** / **"Good morning JARVIS"** | Friendly morning greeting |
| **"Good afternoon"** | Good afternoon response |
| **"Good evening"** | Good evening response |
| **"Good night"** | Good night response |
| **"How are you?"** / **"How are you doing?"** | Friendly status response |
| **"Compliment me"** / **"Say something nice"** | Receives a compliment |
| **"I am bored"** / **"Feeling bored"** | Suggests activities |
| **"Tell me a quote"** / **"Inspire me"** / **"Motivate me"** | Shares a motivational quote |
| **"Tell me a fact"** / **"Fun fact"** / **"Random fact"** | Shares an interesting fact |
| **"Cheer me up"** / **"I feel sad"** | Uplifting response |
| **"Thank you"** / **"Thanks a lot"** | Gracious reply |
| **"Repeat that"** / **"Say that again"** | Repeats last JARVIS response |
| **"Help"** / **"What can you do?"** | Lists capabilities |
| **"Exit"** / **"Quit"** / **"Goodbye"** | Closes JARVIS |

---

## 🗣️ Tips for Best Recognition

1. **Speak clearly** at normal conversation speed
2. **Pause briefly** (0.5s) before and after your command
3. **Natural phrasing** works — "play some lofi music on YouTube" works great
4. **Fallback:** If JARVIS doesn't recognize a command exactly, it does a **fuzzy match** — so close approximations still work
5. **Google Search Fallback:** Completely unknown phrases are searched on Google automatically

---

*JARVIS — Always online, always listening.* 🎙️
