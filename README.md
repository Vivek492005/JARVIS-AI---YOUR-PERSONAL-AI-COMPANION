# 🚀 JARVIS: Your Personal AI Companion

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![LLM](https://img.shields.io/badge/Brain-Qwen%202.5%2072B%20%2F%20DeepSeek-orange.svg)](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct)
[![Voice](https://img.shields.io/badge/Voice-Rumik%20AI%20Silk%20TTS-purple.svg)](https://rumik.ai/)
[![OS](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6.svg)](https://www.microsoft.com/windows/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/Vivek492005/JARVIS-AI---YOUR-PERSONAL-AI-COMPANION?style=social)](https://github.com/Vivek492005/JARVIS-AI---YOUR-PERSONAL-AI-COMPANION/stargazers)

**JARVIS** is an intelligent, autonomous hands-free voice and text assistant for Windows. Unlike legacy voice assistants that rely on rigid regex keywords or predefined patterns, JARVIS is driven by **state-of-the-art Large Language Models (Qwen 2.5 72B Instruct via Hugging Face Router and DeepSeek V4)** paired with an **autonomous tool-calling engine** and **Rumik AI Silk TTS voice synthesis**.

Whether you speak in casual English, Hindi, Hinglish, or give complex multi-action instructions, JARVIS understands intent dynamically, performs real-world desktop operations, controls OS settings, queries the web, writes notes, downloads media, and speaks back naturally — with your voice, on your machine, entirely under your control.

---

## 📖 Table of Contents

- [Quick Start](#-quick-start)
- [Key Capabilities](#-key-capabilities--highlights)
- [Project Architecture](#-project-architecture--organization)
- [Detailed Installation](#️-detailed-installation--setup)
- [API Key Configuration](#-api-key-configuration)
- [Running JARVIS](#-running-jarvis)
- [Voice & Gesture Commands](#-how-to-interact-with-jarvis)
- [How It Works Internally](#-how-jarvis-works-internally)
- [Testing & Diagnostics](#-running-tests--diagnostics)
- [Troubleshooting](#-troubleshooting)
- [Security & Privacy](#-security--privacy)
- [Roadmap](#-roadmap--future-scope)
- [Contributing](#-contributing)
- [License](#-license)

---

## ⚡ Quick Start

Already have Python 3.10+ installed? You'll be talking to JARVIS in under 5 minutes.

```powershell
# 1. Clone the repository
git clone https://github.com/Vivek492005/JARVIS-AI---YOUR-PERSONAL-AI-COMPANION.git
cd JARVIS-AI---YOUR-PERSONAL-AI-COMPANION

# 2. Run the installer (creates a virtual environment + installs dependencies)
install.bat

# 3. Add your API keys
copy env.example .env
# → open .env in any text editor and paste in your keys (see API Key Configuration below)

# 4. Launch
Launch_Saarthi.bat
```

That's it — the floating companion widget should appear on your screen and start listening. 🎙

Need API keys first? Jump to [API Key Configuration](#-api-key-configuration) — all three services have a free tier. Something not working? See [Troubleshooting](#-troubleshooting).

---

## 🌟 Key Capabilities & Highlights

### 1. 🧠 Intelligent LLM Brain (Qwen 2.5 72B & DeepSeek)
- **Primary Model**: Alibaba's flagship open-weights model `Qwen/Qwen2.5-72B-Instruct` served via the high-speed Hugging Face Router (`https://router.huggingface.co/v1`).
- **Autonomous Tool/Function Calling**: The LLM parses user speech, determines which local tools to trigger, formats arguments into JSON, runs the action, and synthesizes a concise, spoken reply.
- **Multi-Lingual Natural Interaction**: Speak freely in English, Hindi, or mixed Hinglish (*"Bhai chrome khol de aur latest news search kar"*). No strict keywords required.
- **Context-Aware Rolling Memory**: Keeps sliding conversational context so follow-up commands (*"Now download that"*, *"Make it louder"*, *"Save that as a note"*) work seamlessly.

### 2. 🎙 Human-Like Voice Synthesis (Rumik AI Silk TTS)
- **Primary Voice Engine**: Rumik AI Silk TTS (`https://silk-api.rumik.ai/v1/tts`, model `muga`) generating natural, expressive, lifelike speech.
- **Multi-Tiered Failover** — JARVIS never goes silent:
  ```
  [1] Primary: Rumik AI Silk TTS (High-Definition Cloud Voice)
         │ (if quota expires / connection drops)
         ▼
  [2] Secondary: Microsoft Natural Neural Voice (Edge-TTS en-US-AvaNeural / en-IN-NeerjaNeural)
         │ (if offline)
         ▼
  [3] Tertiary: Pyttsx3 Offline Local Speech Synthesizer
  ```

### 3. 🛠 Autonomous Desktop & Web Tool Suite
- **Application Launcher (`open_application`)**: Fuzzy-matches and launches local software (Google Chrome, VS Code, Notepad, Spotify, Calculator, File Explorer, Terminal, Office apps, etc.).
- **Media Downloader (`download_media`)**: Autonomous search and download of audio (MP3) or video (MP4) to your `Downloads` or `Music` folders using `yt-dlp`.
- **System Automation (`system_control`)**:
  - Volume control (raise, lower, mute, unmute).
  - High-resolution screen capture (`screenshots/screenshot_YYYYMMDD_HHMMSS.png`).
  - Workstation lock (`rundll32 user32.dll,LockWorkStation`).
  - Recycle bin auto-clean and hardware battery status reporting.
- **Keyboard & Typing Automation (`keyboard_mouse_action`)**: Auto-types arbitrary text, pastes clipboard contents, and fires hotkeys (`ctrl+s`, `alt+f4`, `ctrl+c`, `ctrl+v`, etc.).
- **Notes Manager (`manage_notes`)**: Saves, reads, and clears persistent timestamped notes in `notes.txt`.
- **Live Web Research (`web_search` & `open_website`)**: Searches Google or opens specific URLs and web applications.

### 4. 🐶 Floating Companion GUI & Dual-Input Mode
- **Draggable Card Widget**: Frameless, sleek dark-themed companion with a smooth rounded avatar (`puppy.jpg`).
- **Live Status Indicator**: Real-time badge showing agent states (`● Listening...`, `⚡ Thinking...`, `⚡ Downloading...`, `● Ready`).
- **Interactive Prompt Bar**: Instant text entry (`➔`) allows silent keyboard operation alongside microphone voice capture.
- **Microphone Toggle**: Single-click button to pause and resume listening on demand.

### 5. ✋ Gesture Control (MediaPipe)
- Optional webcam-based hand-gesture control layer (`access_os/gesture_controller.py`), runnable standalone via `run_gestures.py`.
- Full gesture reference: [GESTURE_COMMANDS.md](GESTURE_COMMANDS.md).

### 6. 🛡 Zero-Downtime Multi-Level Resiliency
- If the primary API runs out of tokens or drops internet connectivity, the assistant automatically cascades:
  `Hugging Face Qwen 72B ➔ DeepSeek Cloud ➔ Smart Local Heuristic Parser`.
- The assistant **never crashes or freezes**.

---

## 📂 Project Architecture & Organization

```
JARVIS-AI---YOUR-PERSONAL-AI-COMPANION/
│
├── env.example                 # Template for your API keys — copy to .env
├── .gitignore                  # Git hygiene rules (ignoring logs, venv, secrets)
├── LICENSE                     # MIT License
├── voice_config.json           # Voice and AI agent settings (provider, models, thresholds)
├── config.json                 # Global application configuration
├── puppy.jpg                   # Companion GUI avatar image
│
├── main.py                     # Primary GUI application entry point
├── gui.py                      # Tkinter + Pillow floating AI companion widget
├── install.bat                 # One-click dependency & environment setup
├── Launch_Saarthi.bat          # 1-click desktop background launcher
│
├── access_os/                  # Core Accessibility & Intelligence Package
│   ├── __init__.py             # Module exports
│   ├── ai_agent.py             # Qwen 72B / DeepSeek LLM Brain + Tool Dispatcher
│   ├── voice_interface.py      # Audio capture, Rumik/Neural TTS, and Voice processor
│   ├── gesture_controller.py   # MediaPipe gesture tracking & hands-free control
│   └── main.py                 # CLI / Assistive mode entry point
│
├── run_gestures.py             # Standalone gesture controller runner
├── requirements.txt            # Production dependencies
├── requirements-dev.txt        # Development and testing tools
├── setup.py                    # Package installer script
│
├── tests/                      # Consolidated Test & Diagnostic Suite
│   ├── test_ai_agent.py        # End-to-end LLM tool execution & fallback test
│   ├── test_voice.py           # Voice recognition calibration test
│   ├── test_voice_interface.py # Voice pipeline unit tests
│   ├── test_mic.py             # Microphone hardware & noise floor inspection
│   ├── test_gestures.py        # Camera & MediaPipe hand tracking validation
│   └── test_gesture_controller.py # Gesture state machine tests
│
├── GESTURE_COMMANDS.md         # Reference manual for vision gesture controls
├── VOICE_COMMANDS.md           # Reference guide for voice commands & phrases
└── README.md                   # Complete system documentation
```

> **Note**: `.env`, `notes.txt`, `jarvis.log`, `screenshots/`, `.venv/`, and `__pycache__/` are generated at runtime and intentionally excluded from version control via `.gitignore` — you won't see them in a fresh clone.

> ⚠️ **File naming note**: The launcher script is currently named `Launch_Saarthi.bat` (a leftover from an earlier project name). It works exactly the same — just double-click it. For full naming consistency you can rename it to `Launch_JARVIS.bat` in your local copy; just remember to update this README's command if you do.

---

## ⚙️ Detailed Installation & Setup

### 1. Prerequisites
- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python**: Python 3.10 or 3.11 recommended — [download here](https://www.python.org/downloads/) (check **"Add Python to PATH"** during install)
- **Hardware**: A working microphone, and optionally a webcam for gesture control

### 2. Clone the Repository

```powershell
git clone https://github.com/Vivek492005/JARVIS-AI---YOUR-PERSONAL-AI-COMPANION.git
cd JARVIS-AI---YOUR-PERSONAL-AI-COMPANION
```

### 3. Set Up the Environment

**Option A — Automatic (recommended):**
```powershell
install.bat
```
This will:
1. Verify Python is installed and on PATH
2. Create a virtual environment at `.venv` (skips this step if one already exists)
3. Activate it
4. Install every dependency from `requirements.txt`
5. Copy `env.example` to `.env` automatically if one doesn't already exist

**Option B — Manual:**
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy env.example .env
```

---

## 🔑 API Key Configuration

Open the `.env` file you just created and fill in your own keys:

```env
# Primary LLM Brain: Hugging Face with Qwen 2.5 72B Instruct
HUGGINGFACE_API_KEY=your_huggingface_token
HUGGINGFACE_BASE_URL=https://router.huggingface.co/v1
HUGGINGFACE_MODEL=Qwen/Qwen2.5-72B-Instruct

# Secondary Fallback: DeepSeek
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Primary Voice Engine: Rumik AI Silk TTS
RUMIK_API_KEY=your_rumik_key
RUMIK_API_URL=https://silk-api.rumik.ai/v1/tts
RUMIK_MODEL=muga
```

### Where to get each key (all offer a free tier):

| Service | Used for | Get your key here |
|---|---|---|
| Hugging Face | Primary LLM brain (Qwen 2.5 72B) | https://huggingface.co/settings/tokens |
| DeepSeek | Fallback LLM brain | https://platform.deepseek.com/api_keys |
| Rumik AI | Primary voice synthesis (Silk TTS) | https://rumik.ai/ |

> 🔒 **Never commit your real `.env` file.** It's already excluded via `.gitignore`. Only `env.example` (with placeholder values) should ever be pushed to GitHub. If you ever accidentally commit real keys, rotate/regenerate them immediately on the provider's dashboard — deleting the file later does not remove it from git history.

If both Hugging Face and DeepSeek are ever unreachable, JARVIS silently falls back to a local heuristic parser rather than crashing — see [Zero-Downtime Resiliency](#6--zero-downtime-multi-level-resiliency).

---

## 🚀 Running JARVIS

### Option A: Desktop 1-Click Launch (Recommended)
Double-click **`Launch_Saarthi.bat`**.
This starts the floating AI companion without leaving a lingering command prompt open.

### Option B: From Command Line
```powershell
.\.venv\Scripts\python main.py
```

### Option C: Standalone Gesture Controller
```powershell
.\.venv\Scripts\python run_gestures.py
```

---

## 🗣 How to Interact with JARVIS

### Natural Spoken Commands (Microphone)
Speak naturally at any time — no wake word or rigid syntax required:
- *"Can you open Google Chrome and find the latest developments in AI?"*
- *"Open Notepad and write down my grocery list."*
- *"Download song Believer by Imagine Dragons."*
- *"Take a screenshot of my screen."*
- *"Mute the audio and lock my computer."*
- *"What is my current battery percentage?"*
- *"Note that project milestone 1 is officially completed."*
- *"Read out my latest notes."*
- *"Bhai Chrome khol de aur latest news search kar"* (Hinglish works too)

📖 Full reference: [VOICE_COMMANDS.md](VOICE_COMMANDS.md)

### Hands-Free Gesture Commands
For touch-free control via webcam (volume, navigation, clicks), see the complete gesture mapping:

📖 Full reference: [GESTURE_COMMANDS.md](GESTURE_COMMANDS.md)

### Interactive Prompt Bar (Companion Card)
Prefer to type? Use the input bar on the companion card:
1. Type your command (e.g. `Download video Python in 100 seconds`).
2. Press **Enter** or click `➔`.
3. JARVIS executes the tool and gives visual and spoken confirmation.

---

## 🧠 How JARVIS Works Internally

A quick mental model of the request lifecycle, for anyone reading the code or contributing:

1. **Capture** — `voice_interface.py` listens via microphone (speech-to-text) or reads text typed into the prompt bar.
2. **Understand** — the captured input, plus recent rolling conversational context, is sent to `ai_agent.py`, which calls the LLM brain (Qwen 2.5 72B via Hugging Face, falling back to DeepSeek).
3. **Decide** — the LLM doesn't just reply in text; it decides *which tool to call* (open an app, download media, control the system, etc.) and formats the arguments as structured JSON — this is the "autonomous tool-calling" mechanism.
4. **Execute** — the tool dispatcher in `ai_agent.py` runs the corresponding function in `access_os/` against your actual OS (via `pyautogui`, `subprocess`, `yt-dlp`, etc.), inside white-listed, sandboxed calls.
5. **Respond** — the result is summarized into a short natural-language reply, sent to `voice_interface.py`, and spoken back through the TTS failover chain (Rumik → Edge-TTS → Pyttsx3).
6. **Reflect** — the GUI (`gui.py`) updates its live status badge throughout (`● Listening...` → `⚡ Thinking...` → `● Ready`) so you always know what state JARVIS is in.

---

## 🧪 Running Tests & Diagnostics

All diagnostic and verification tests are organized in `tests/`:

```powershell
# Test the full LLM agent, tool calling, and failover engine:
.\.venv\Scripts\python tests/test_ai_agent.py

# Test microphone hardware and noise threshold calibration:
.\.venv\Scripts\python tests/test_mic.py

# Test speech recognition accuracy:
.\.venv\Scripts\python tests/test_voice.py

# Test the full voice pipeline end-to-end:
.\.venv\Scripts\python tests/test_voice_interface.py

# Test camera and MediaPipe hand tracking:
.\.venv\Scripts\python tests/test_gestures.py

# Test the gesture state machine:
.\.venv\Scripts\python tests/test_gesture_controller.py
```

Run these first whenever something doesn't behave as expected — they'll usually pinpoint whether the issue is your mic, your API keys, or your camera before you dig into the main application.

---

## 🛠 Troubleshooting

| Problem | Fix |
|---|---|
| `install.bat` says Python not found | Install Python 3.10+ from python.org and ensure "Add Python to PATH" was checked during install, then restart PowerShell. |
| JARVIS launches but doesn't respond to voice | Run `tests/test_mic.py` to confirm your microphone is detected and calibrated correctly. |
| API errors on startup | Double-check `.env` has no extra quotes or spaces around your keys, and that each key is still active on its provider's dashboard. |
| Voice sounds robotic / TTS fails silently | This means JARVIS has fallen back to the tertiary (offline) voice engine — check your internet connection and your Rumik/Edge-TTS quota. |
| `pip install` fails midway | Delete the `.venv` folder and re-run `install.bat` for a clean environment. |
| Gesture control doesn't detect hands | Run `tests/test_gestures.py` to confirm your webcam is accessible and well-lit; MediaPipe needs decent lighting to track landmarks reliably. |
| `.env` not being picked up | Confirm the file is named exactly `.env` (not `.env.txt` or `env`) and sits in the project root, next to `main.py`. |

---

## 🔒 Security & Privacy
- **API Keys**: All credentials are kept in `.env` (never committed) and excluded from version control via `.gitignore`. Only `env.example`, with placeholder values, is tracked in the repo.
- **System Safety**: Command execution uses verified white-listed system calls and sandboxed parameter verification — JARVIS won't run arbitrary shell commands from LLM output.
- **Fail-Safe Operation**: `pyautogui.FAILSAFE` protections are integrated to prevent runaway cursor movements (move your mouse to a screen corner to force-abort any automated action).
- **Local-First Notes**: Notes are stored locally in `notes.txt` and never transmitted anywhere outside your machine.

---

## 🗺 Roadmap & Future Scope

Ideas for where this project could go next (contributions welcome on any of these):

- [ ] Cross-platform support (macOS / Linux) for the core tool suite
- [ ] Plugin system for community-contributed tools
- [ ] Local/offline LLM option (e.g. via Ollama) as a fourth resiliency tier
- [ ] Packaged installer (`.exe`) for non-technical users, removing the need to manually run Python setup steps
- [ ] Web-based dashboard for reviewing notes and command history

---

## 🤝 Contributing

Contributions are welcome! To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature-name`)
3. Make your changes and test them using the diagnostic suite in `tests/`
4. Commit with a clear message and open a pull request

For larger changes, please open an issue first to discuss what you'd like to change.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<p align="center">Built with ❤️ by <a href="https://github.com/Vivek492005">Vivek Bartwal</a></p>
