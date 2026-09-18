"""
AIAgent - DeepSeek & LLM Intelligent Brain with Autonomous Tool Calling for JARVIS.

Features:
- Understands multi-lingual & conversational input (English, Hindi, Hinglish, etc.).
- Autonomous Tool / Function Calling:
    * open_application(app_name)
    * open_website(url_or_name)
    * web_search(query)
    * download_media(url_or_query, media_type)
    * system_control(action, value)
    * keyboard_mouse_action(action, text, shortcut)
    * manage_notes(action, content)
    * run_powershell_command(command)
- Conversation history tracking with sliding window.
- Resilient fallback execution when API balance or network is unavailable.
"""

import os
import sys
import json
import logging
import datetime
import subprocess
import webbrowser
import urllib.parse
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)

# Ensure python-dotenv is loaded if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class AIAgent:
    """Intelligent reasoning and tool execution engine for JARVIS / JARVIS."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        status_callback: Optional[Callable[[str], None]] = None,
        provider: str = "huggingface",
    ):
        self.provider = provider or os.getenv("AI_PROVIDER", "huggingface")
        
        # Primary: Hugging Face with Qwen 2.5 72B Instruct
        self.hf_api_key = os.getenv("HUGGINGFACE_API_KEY", "")
        self.hf_base_url = os.getenv("HUGGINGFACE_BASE_URL", "https://router.huggingface.co/v1")
        self.hf_model = model or os.getenv("HUGGINGFACE_MODEL", "Qwen/Qwen2.5-72B-Instruct")

        # Secondary: DeepSeek
        self.ds_api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.ds_base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.ds_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        self.model = self.hf_model if self.provider == "huggingface" else self.ds_model
        self.temperature = temperature
        self.status_callback = status_callback
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = 10
        self.notes_file = "notes.txt"

        self.client = None
        self.backup_client = None
        self._init_clients()
        self._init_tools()

    def _notify_status(self, msg: str):
        if self.status_callback:
            try:
                self.status_callback(msg)
            except Exception:
                pass

    def _init_clients(self):
        """Initialize primary (Hugging Face Qwen) and secondary (DeepSeek) clients."""
        from openai import OpenAI

        # 1. Initialize Hugging Face Client
        if self.hf_api_key:
            try:
                self.client = OpenAI(api_key=self.hf_api_key, base_url=self.hf_base_url)
                logger.info(f"Primary AI client initialized (Hugging Face: {self.hf_model})")
            except Exception as e:
                logger.error(f"Failed to initialize Hugging Face client: {e}")
                self.client = None

        # 2. Initialize DeepSeek Backup Client
        if self.ds_api_key:
            try:
                self.backup_client = OpenAI(api_key=self.ds_api_key, base_url=self.ds_base_url)
                logger.info(f"Secondary AI client initialized (DeepSeek: {self.ds_model})")
            except Exception as e:
                logger.error(f"Failed to initialize DeepSeek backup client: {e}")
                self.backup_client = None

    def _init_tools(self):
        """Define OpenAI-compatible tool specifications."""
        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "open_application",
                    "description": "Opens or launches an application or program installed on the Windows PC (e.g. Chrome, Notepad, VS Code, Calculator, Spotify, WhatsApp, Word, Excel, File Explorer, Command Prompt, etc.).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "app_name": {
                                "type": "string",
                                "description": "The common name of the application to launch (e.g. 'chrome', 'notepad', 'calculator', 'spotify', 'code', 'file explorer')."
                            }
                        },
                        "required": ["app_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "open_website",
                    "description": "Opens a specific website or web portal in the user's default browser.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url_or_name": {
                                "type": "string",
                                "description": "The URL (e.g. 'https://youtube.com') or website name (e.g. 'youtube', 'github', 'linkedin', 'netflix', 'amazon')."
                            }
                        },
                        "required": ["url_or_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Searches Google or the web for real-time information, answers, queries, or news requested by the user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query."
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "download_media",
                    "description": "Downloads video or audio from YouTube or any media URL, or searches and downloads the requested song or video using yt-dlp.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url_or_query": {
                                "type": "string",
                                "description": "The media URL or the search term of the song/video to download."
                            },
                            "media_type": {
                                "type": "string",
                                "enum": ["audio", "video"],
                                "description": "Whether to download audio (mp3/m4a) or video (mp4). Defaults to audio for songs, video otherwise."
                            }
                        },
                        "required": ["url_or_query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "system_control",
                    "description": "Controls Windows OS system functions: volume adjustments, mute, screenshot capture, lock workstation, empty recycle bin, battery check.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": [
                                    "volume_up",
                                    "volume_down",
                                    "mute",
                                    "unmute",
                                    "take_screenshot",
                                    "lock_pc",
                                    "empty_recycle_bin",
                                    "check_battery"
                                ],
                                "description": "The specific system action to perform."
                            }
                        },
                        "required": ["action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "keyboard_mouse_action",
                    "description": "Performs typing, keyboard hotkeys (like save, copy, paste, select all, close window), or text entry into the active window.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["type_text", "press_hotkey", "press_key"],
                                "description": "The action type."
                            },
                            "value": {
                                "type": "string",
                                "description": "The text to type or the hotkey combination (e.g. 'ctrl+s', 'ctrl+c', 'ctrl+v', 'alt+f4', 'enter', 'esc')."
                            }
                        },
                        "required": ["action", "value"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "manage_notes",
                    "description": "Saves a note, reads saved notes, or clears saved user notes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["save", "read", "clear"],
                                "description": "Action to perform on notes."
                            },
                            "content": {
                                "type": "string",
                                "description": "Content of the note if saving."
                            }
                        },
                        "required": ["action"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_powershell_command",
                    "description": "Runs a safe, non-destructive PowerShell command for general OS queries or file lookups.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The PowerShell command string to execute."
                            }
                        },
                        "required": ["command"]
                    }
                }
            }
        ]

    def _get_system_prompt(self) -> str:
        current_time = datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
        return (
            f"You are JARVIS (also known as JARVIS), an intelligent, highly capable production-grade AI Assistant "
            f"and Windows OS Copilot. Current local time: {current_time}.\n\n"
            "Capabilities & Behavior:\n"
            "1. You understand natural speech and queries in ANY language (English, Hindi, Hinglish, Spanish, etc.).\n"
            "2. When the user asks to perform an action (open apps, open sites, download music/videos, write text, "
            "search the web, take screenshots, lock PC, adjust volume, take notes, etc.), autonomously call the relevant tool.\n"
            "3. If multiple actions are requested in one sentence (e.g., 'open notepad and write hello'), call the tools in sequence.\n"
            "4. For general questions, jokes, explanations, or conversational chit-chat, respond directly in a warm, concise, "
            "helpful manner suitable for Text-To-Speech (keep it natural, punchy, avoid complex markdown or long code blocks unless asked).\n"
            "5. Always confirm actions politely and briefly (e.g., 'Opening Chrome', 'Downloaded song to your Downloads folder')."
        )

    # =========================================================================
    # TOOL EXECUTION IMPLEMENTATIONS
    # =========================================================================

    def execute_open_application(self, app_name: str) -> str:
        self._notify_status(f"Opening {app_name}...")
        lowered = app_name.lower().strip()

        app_mappings = {
            "chrome": ["start", "chrome"],
            "google chrome": ["start", "chrome"],
            "edge": ["start", "msedge"],
            "ms edge": ["start", "msedge"],
            "microsoft edge": ["start", "msedge"],
            "notepad": ["notepad.exe"],
            "calculator": ["calc.exe"],
            "calc": ["calc.exe"],
            "vs code": ["code"],
            "vscode": ["code"],
            "code": ["code"],
            "file explorer": ["explorer.exe"],
            "explorer": ["explorer.exe"],
            "terminal": ["wt.exe"],
            "command prompt": ["cmd.exe"],
            "cmd": ["cmd.exe"],
            "powershell": ["powershell.exe"],
            "task manager": ["taskmgr.exe"],
            "paint": ["mspaint.exe"],
            "settings": ["start", "ms-settings:"],
            "spotify": ["start", "spotify:"],
            "word": ["start", "winword"],
            "excel": ["start", "excel"],
            "powerpoint": ["start", "powerpnt"],
        }

        for key, cmd in app_mappings.items():
            if key in lowered or lowered in key:
                try:
                    subprocess.Popen(cmd, shell=True)
                    return f"Successfully opened {app_name}."
                except Exception as e:
                    logger.error(f"Failed to open mapped app {app_name}: {e}")

        # Try generic Windows start
        try:
            subprocess.Popen(f'start "" "{app_name}"', shell=True)
            return f"Opened {app_name}."
        except Exception as e:
            logger.error(f"Failed to start app {app_name}: {e}")
            return f"Could not launch {app_name}: {e}"

    def execute_open_website(self, url_or_name: str) -> str:
        self._notify_status(f"Opening {url_or_name}...")
        url = url_or_name.strip()
        site_map = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "gmail": "https://mail.google.com",
            "github": "https://github.com",
            "linkedin": "https://www.linkedin.com",
            "twitter": "https://twitter.com",
            "x": "https://twitter.com",
            "instagram": "https://www.instagram.com",
            "facebook": "https://www.facebook.com",
            "reddit": "https://www.reddit.com",
            "netflix": "https://www.netflix.com",
            "spotify": "https://open.spotify.com",
            "amazon": "https://www.amazon.com",
            "chatgpt": "https://chat.openai.com",
            "whatsapp": "https://web.whatsapp.com",
            "wikipedia": "https://www.wikipedia.org",
        }

        lowered = url.lower()
        for name, full_url in site_map.items():
            if lowered == name or lowered == f"open {name}":
                webbrowser.open(full_url)
                return f"Opening {name}."

        if not url.startswith("http://") and not url.startswith("https://"):
            if "." in url and " " not in url:
                url = "https://" + url
            else:
                return self.execute_web_search(url)

        webbrowser.open(url)
        return f"Opening {url_or_name}."

    def execute_web_search(self, query: str) -> str:
        self._notify_status(f"Searching web for '{query}'...")
        encoded = urllib.parse.quote_plus(query)
        webbrowser.open(f"https://www.google.com/search?q={encoded}")
        return f"Searching Google for {query}."

    def execute_download_media(self, url_or_query: str, media_type: str = "audio") -> str:
        self._notify_status(f"Downloading {media_type} for '{url_or_query}'...")
        try:
            import yt_dlp

            # Determine download path (user's Downloads or Music directory)
            home_dir = os.path.expanduser("~")
            if media_type == "audio":
                download_dir = os.path.join(home_dir, "Music")
            else:
                download_dir = os.path.join(home_dir, "Downloads")
            os.makedirs(download_dir, exist_ok=True)

            out_template = os.path.join(download_dir, "%(title)s.%(ext)s")

            ydl_opts = {
                "outtmpl": out_template,
                "quiet": True,
                "no_warnings": True,
            }

            if media_type == "audio":
                ydl_opts["format"] = "bestaudio/best"
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
            else:
                ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

            # If input is not a direct URL, use ytsearch
            target = url_or_query.strip()
            if not target.startswith("http://") and not target.startswith("https://"):
                target = f"ytsearch1:{target}"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target, download=True)
                title = info.get("title", "media")
                if "entries" in info and len(info["entries"]) > 0:
                    title = info["entries"][0].get("title", title)

            folder_name = "Music" if media_type == "audio" else "Downloads"
            return f"Successfully downloaded '{title}' to your {folder_name} folder."
        except Exception as e:
            logger.error(f"Download error: {e}")
            return f"Download failed: {str(e)}"

    def execute_system_control(self, action: str) -> str:
        self._notify_status(f"Executing system control: {action}...")
        try:
            import pyautogui

            if action == "volume_up":
                for _ in range(5):
                    pyautogui.press("volumeup")
                return "Increased volume."
            elif action == "volume_down":
                for _ in range(5):
                    pyautogui.press("volumedown")
                return "Decreased volume."
            elif action in ["mute", "unmute"]:
                pyautogui.press("volumemute")
                return "Toggled volume mute."
            elif action == "take_screenshot":
                os.makedirs("screenshots", exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                fn = os.path.join("screenshots", f"screenshot_{ts}.png")
                screenshot = pyautogui.screenshot()
                screenshot.save(fn)
                return f"Screenshot captured and saved to {fn}."
            elif action == "lock_pc":
                os.system("rundll32.exe user32.dll,LockWorkStation")
                return "Locking the workstation."
            elif action == "empty_recycle_bin":
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                )
                return "Recycle Bin has been emptied."
            elif action == "check_battery":
                try:
                    import psutil
                    battery = psutil.sensors_battery()
                    if battery:
                        plugged = "plugged in" if battery.power_plugged else "on battery"
                        return f"Battery is at {battery.percent:.0f}% and {plugged}."
                except Exception:
                    pass
                return "Battery status is unavailable."
            return f"Unknown system action: {action}"
        except Exception as e:
            logger.error(f"System control error ({action}): {e}")
            return f"Failed to perform {action}: {e}"

    def execute_keyboard_mouse(self, action: str, value: str) -> str:
        self._notify_status(f"Performing {action}...")
        try:
            import pyautogui
            import pyperclip

            if action == "type_text":
                pyperclip.copy(value)
                pyautogui.hotkey("ctrl", "v")
                return f"Typed: '{value}'"
            elif action == "press_hotkey":
                keys = [k.strip().lower() for k in value.split("+")]
                pyautogui.hotkey(*keys)
                return f"Pressed hotkey {value}."
            elif action == "press_key":
                pyautogui.press(value.lower().strip())
                return f"Pressed key {value}."
            return f"Unknown keyboard action: {action}"
        except Exception as e:
            logger.error(f"Keyboard/mouse action error: {e}")
            return f"Action failed: {e}"

    def execute_manage_notes(self, action: str, content: Optional[str] = None) -> str:
        self._notify_status("Managing notes...")
        if action == "save":
            if not content:
                return "No note content provided."
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.notes_file, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {content}\n")
            return f"Note saved: {content}"
        elif action == "read":
            if not os.path.exists(self.notes_file):
                return "You do not have any notes saved yet."
            with open(self.notes_file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            if not lines:
                return "Your notes file is empty."
            recent = lines[-5:]
            return "Here are your recent notes: " + " | ".join(recent)
        elif action == "clear":
            if os.path.exists(self.notes_file):
                os.remove(self.notes_file)
            return "Cleared all your notes."
        return f"Unknown note action: {action}"

    def execute_powershell(self, command: str) -> str:
        self._notify_status(f"Running command: {command}...")
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            output = result.stdout.strip() or result.stderr.strip()
            return output[:300] if output else "Command executed successfully."
        except Exception as e:
            logger.error(f"PowerShell execution error: {e}")
            return f"Command execution failed: {e}"

    def _dispatch_tool_call(self, function_name: str, args: Dict[str, Any]) -> str:
        """Route tool call to appropriate Python handler."""
        logger.info(f"Executing tool: {function_name} with args: {args}")

        if function_name == "open_application":
            return self.execute_open_application(args.get("app_name", ""))
        elif function_name == "open_website":
            return self.execute_open_website(args.get("url_or_name", ""))
        elif function_name == "web_search":
            return self.execute_web_search(args.get("query", ""))
        elif function_name == "download_media":
            return self.execute_download_media(
                args.get("url_or_query", ""),
                args.get("media_type", "audio")
            )
        elif function_name == "system_control":
            return self.execute_system_control(args.get("action", ""))
        elif function_name == "keyboard_mouse_action":
            return self.execute_keyboard_mouse(
                args.get("action", ""),
                args.get("value", "")
            )
        elif function_name == "manage_notes":
            return self.execute_manage_notes(
                args.get("action", ""),
                args.get("content", None)
            )
        elif function_name == "run_powershell_command":
            return self.execute_powershell(args.get("command", ""))
        else:
            return f"Tool {function_name} is not recognized."

    # =========================================================================
    # INTENT PROCESSING & FALLBACK REASONING
    # =========================================================================

    def _local_fallback_process(self, user_input: str) -> str:
        """Heuristic-based intelligent fallback if API balance is empty or offline."""
        lowered = user_input.lower().strip()

        # 1. Download requests
        if "download" in lowered or "song" in lowered or "video" in lowered:
            media_type = "audio" if ("song" in lowered or "music" in lowered or "mp3" in lowered) else "video"
            query = user_input
            for phrase in ["download song", "download video", "download", "please download"]:
                if phrase in query.lower():
                    query = query.lower().replace(phrase, "").strip()
            if query:
                return self.execute_download_media(query, media_type)

        # 2. Open Application / Website requests
        if lowered.startswith("open ") or lowered.startswith("launch ") or lowered.startswith("go to "):
            target = lowered.replace("open ", "").replace("launch ", "").replace("go to ", "").strip()
            # If known website or dot in name
            if any(s in target for s in ["youtube", "google", "gmail", "github", "linkedin", "reddit", "netflix", "instagram", "facebook", "twitter", "whatsapp", "chatgpt"]) or "." in target:
                return self.execute_open_website(target)
            return self.execute_open_application(target)

        # 3. Write / Type text
        if lowered.startswith("write ") or lowered.startswith("type "):
            text = user_input
            for prefix in ["write that ", "write ", "type that ", "type "]:
                if lowered.startswith(prefix):
                    text = user_input[len(prefix):].strip()
                    break
            return self.execute_keyboard_mouse("type_text", text)

        # 4. Search requests
        if "search for" in lowered or "search google for" in lowered or lowered.startswith("google "):
            for prefix in ["search google for ", "search for ", "google for ", "google "]:
                if prefix in lowered:
                    idx = lowered.find(prefix) + len(prefix)
                    query = user_input[idx:].strip()
                    return self.execute_web_search(query)

        # 5. System commands
        if "screenshot" in lowered:
            return self.execute_system_control("take_screenshot")
        if "lock" in lowered and ("pc" in lowered or "computer" in lowered or "workstation" in lowered):
            return self.execute_system_control("lock_pc")
        if "recycle bin" in lowered:
            return self.execute_system_control("empty_recycle_bin")
        if "battery" in lowered:
            return self.execute_system_control("check_battery")
        if "volume up" in lowered or "increase volume" in lowered:
            return self.execute_system_control("volume_up")
        if "volume down" in lowered or "decrease volume" in lowered:
            return self.execute_system_control("volume_down")
        if "mute" in lowered:
            return self.execute_system_control("mute")

        # 6. Notes
        if lowered.startswith("note that ") or lowered.startswith("take note ") or lowered.startswith("save note "):
            content = user_input
            for p in ["note that ", "take note ", "save note "]:
                if lowered.startswith(p):
                    content = user_input[len(p):].strip()
                    break
            return self.execute_manage_notes("save", content)
        if "read my notes" in lowered or "show my notes" in lowered:
            return self.execute_manage_notes("read")

        # Default fallback: search query
        return self.execute_web_search(user_input)

    def _call_llm_flow(self, client, model_name: str, clean_input: str) -> Optional[str]:
        """Execute LLM chat completion with autonomous tool dispatch."""
        messages = [{"role": "system", "content": self._get_system_prompt()}]
        for item in self.conversation_history[-self.max_history:]:
            messages.append(item)
        messages.append({"role": "user", "content": clean_input})

        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=self.tool_definitions,
            tool_choice="auto",
            temperature=self.temperature,
        )

        choice = response.choices[0]
        message = choice.message

        # Case 1: Model called one or more tools
        if message.tool_calls:
            messages.append(message)
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                try:
                    func_args = json.loads(tool_call.function.arguments)
                except Exception:
                    func_args = {}

                result_str = self._dispatch_tool_call(func_name, func_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_str
                })

            # Synthesize final spoken response
            final_response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=self.temperature,
            )
            reply = final_response.choices[0].message.content.strip()
            return reply

        # Case 2: Direct conversational answer
        return message.content.strip() if message.content else "I have completed your request."

    def process(self, user_input: str) -> str:
        """Process user input through Qwen 72B (primary), falling back to DeepSeek and then local engine."""
        clean_input = user_input.strip()
        if not clean_input:
            return ""

        self._notify_status("Thinking...")

        # 1. Attempt Primary Client (Hugging Face: Qwen 2.5 72B Instruct)
        if self.client:
            try:
                reply = self._call_llm_flow(self.client, self.model, clean_input)
                if reply:
                    self.conversation_history.append({"role": "user", "content": clean_input})
                    self.conversation_history.append({"role": "assistant", "content": reply})
                    return reply
            except Exception as e:
                logger.warning(f"Primary model ({self.model}) error: {e}. Trying backup client...")

        # 2. Attempt Backup Client (DeepSeek)
        if self.backup_client:
            try:
                reply = self._call_llm_flow(self.backup_client, self.ds_model, clean_input)
                if reply:
                    self.conversation_history.append({"role": "user", "content": clean_input})
                    self.conversation_history.append({"role": "assistant", "content": reply})
                    return reply
            except Exception as e:
                logger.warning(f"Backup model ({self.ds_model}) error: {e}. Switching to intelligent local fallback.")

        # 3. Seamless intelligent local fallback
        reply = self._local_fallback_process(clean_input)
        self.conversation_history.append({"role": "user", "content": clean_input})
        self.conversation_history.append({"role": "assistant", "content": reply})
        return reply
