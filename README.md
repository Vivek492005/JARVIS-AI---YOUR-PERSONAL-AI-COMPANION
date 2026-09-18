# 🚀 JARVIS: Autonomous Production-Grade AI Operating Copilot

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![LLM](https://img.shields.io/badge/Brain-Qwen%202.5%2072B%20%2F%20DeepSeek-orange.svg)](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct)
[![Voice](https://img.shields.io/badge/Voice-Rumik%20AI%20Silk%20TTS-purple.svg)](https://rumik.ai/)
[![OS](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6.svg)](https://www.microsoft.com/windows/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**JARVIS** (also known as **JARVIS**) is an intelligent, autonomous hands-free voice and text assistant for Windows. Unlike legacy voice assistants that rely on rigid regex keywords or predefined patterns, JARVIS is driven by **state-of-the-art Large Language Models (Qwen 2.5 72B Instruct via Hugging Face Router and DeepSeek V4)** paired with an **autonomous tool-calling engine** and **Rumik AI Silk TTS voice synthesis**.

Whether you speak in casual English, Hindi, Hinglish, or give complex multi-action instructions, JARVIS understands intent dynamically, performs real-world desktop operations, controls OS settings, queries the web, writes notes, downloads media, and speaks back naturally.

---

## 🌟 Key Capabilities & Highlights

### 1. 🧠 Intelligent LLM Brain (Qwen 2.5 72B & DeepSeek)
- **Primary Model**: Alibaba's flagship open-weights model `Qwen/Qwen2.5-72B-Instruct` served via the high-speed Hugging Face Router (`https://router.huggingface.co/v1`).
- **Autonomous Tool/Function Calling**: The LLM parses user speech, determines which local tools to trigger, formats arguments into JSON, runs the action, and synthesizes a concise, spoken reply.
- **Multi-Lingual Natural Interaction**: Speak freely in English, Hindi, or mixed Hinglish (*"Bhai chrome khol de aur latest news search kar"*). No strict keywords required.
- **Context-Aware Rolling Memory**: Keeps sliding conversational context so follow-up commands (*"Now download that"*, *"Make it louder"*, *"Save that as a note"*) work seamlessly.

### 2. 🎙 Human-Like Voice Synthesis (Rumik AI Silk TTS)
- **Primary Voice Engine**: Rumik AI Silk TTS (`https://silk-api.rumik.ai/v1/tts`, model `muga`) generating natural, expressive, lifelike speech.
- **Multi-Tiered Failover**:
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
- **Draggable Card Widget**: Frameless, sleek dark-themed companion with smooth rounded avatar.
- **Live Status Indicator**: Real-time badge showing agent states (`● Listening...`, `⚡ Thinking...`, `⚡ Downloading...`, `● Ready`).
- **Interactive Prompt Bar**: Instant text entry (`➔`) allows silent keyboard operation alongside microphone voice capture.
- **Microphone Toggle**: Single-click button to pause and resume listening on demand.

### 5. 🛡 Zero-Downtime Multi-Level Resiliency
- If the primary API runs out of tokens or drops internet connectivity, the assistant automatically cascades:
  `Hugging Face Qwen 72B ➔ DeepSeek Cloud ➔ Smart Local Heuristic Parser`.
- The assistant **never crashes or freezes**.

---

## 📂 Project Architecture & Organization

```
JARVIS/
│
├── .env                        # Secure API keys (Hugging Face, DeepSeek, Rumik AI)
├── .gitignore                  # Git hygiene rules (ignoring logs, venv, secrets)
├── voice_config.json           # Voice and AI agent settings (provider, models, thresholds)
├── config.json                 # Global application configuration
├── puppy.jpg                   # Companion GUI avatar image
│
├── main.py                     # Primary GUI application entry point
├── gui.py                      # Tkinter + Pillow floating AI companion widget
├── Launch_JARVIS.bat          # 1-click desktop background launcher
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

---

## ⚙️ Installation & Setup

### 1. Prerequisites
- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python**: Python 3.10 or 3.11 recommended
- **Hardware**: Working microphone and (optional) webcam for gesture control

### 2. Clone & Environment Setup
Open PowerShell in the project directory:
```powershell
# 1. Activate the existing virtual environment (or create one)
.\.venv\Scripts\activate

# 2. Install all required dependencies
pip install -r requirements.txt
```

### 3. API Key Configuration
Configure your `.env` file in the project root:
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

---

## 🚀 Running JARVIS

### Option A: Desktop 1-Click Launch (Recommended)
Double-click **`Launch_JARVIS.bat`**.
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
Speak naturally at any time:
- *"Can you open Google Chrome and find the latest developments in AI?"*
- *"Open Notepad and write down my grocery list."*
- *"Download song Believer by Imagine Dragons."*
- *"Take a screenshot of my screen."*
- *"Mute the audio and lock my computer."*
- *"What is my current battery percentage?"*
- *"Note that project milestone 1 is officially completed."*
- *"Read out my latest notes."*

### Interactive Prompt Bar (Companion Card)
Prefer to type? Use the input bar on the companion card:
1. Type your command (e.g. `Download video Python in 100 seconds`).
2. Press **Enter** or click `➔`.
3. JARVIS executes the tool and gives visual and spoken confirmation.

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

# Test camera and MediaPipe hand tracking:
.\.venv\Scripts\python tests/test_gestures.py
```

---

## 🔒 Security & Privacy
- **API Keys**: All credentials are kept in `.env` and excluded from version control via `.gitignore`.
- **System Safety**: Command execution uses verified white-listed system calls and sandboxed parameter verification.
- **Fail-Safe Operation**: `pyautogui.FAILSAFE` protections are integrated to prevent runaway cursor movements.

---

## 📄 License
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
