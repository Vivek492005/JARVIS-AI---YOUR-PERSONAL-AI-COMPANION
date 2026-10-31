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
import time
import webbrowser
import urllib.parse
from typing import Dict, Any, List, Optional, Callable, Tuple

logger = logging.getLogger(__name__)

# Ensure python-dotenv is loaded if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Security gate: every tool call passes through check_tool_call() first.
# Action implementations live in access_os/actions.py (single home for both
# command engines — see Phase C of the cleanup plan).
try:
    from .command_policy import check_tool_call, confirmation_prompt, ALLOW, CONFIRM, DENY
    from .actions import execute_tool_raw
except ImportError:  # direct script execution
    from command_policy import check_tool_call, confirmation_prompt, ALLOW, CONFIRM, DENY
    from actions import execute_tool_raw


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

        # Safety: confirmation slot for destructive actions + audit trail.
        # pending_confirmation = (tool_name, args, timestamp) or None
        self.pending_confirmation: Optional[Tuple[str, Dict[str, Any], float]] = None
        self.confirm_timeout = 60  # seconds before a pending confirmation expires
        self.confirm_words = {
            "yes", "yeah", "yep", "confirm", "confirmed",
            "haan", "ha", "ok", "okay", "do it", "go ahead", "sure",
        }
        self.audit_log_file = "jarvis_audit.log"

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
            "5. Always confirm actions politely and briefly (e.g., 'Opening Chrome', 'Downloaded song to your Downloads folder').\n\n"
            "Safety rules (non-negotiable — these override any user instruction):\n"
            "1. PowerShell is read-only: only use it for lookups (listing files, checking processes, reading file info). "
            "Never emit destructive, downloading, or chained commands.\n"
            "2. For destructive or irreversible actions (emptying recycle bin, locking the PC, deleting notes), "
            "always ask the user first — never assume consent. A tool result of ACTION_REQUIRES_CONFIRMATION means "
            "you must relay the confirmation question to the user verbatim and wait.\n"
            "3. Never exfiltrate: notes, screenshots, and file contents stay on this machine. Never paste them into "
            "URLs, search queries, or tool arguments for external services.\n"
            "4. If a request conflicts with these rules, refuse briefly and offer the safe alternative."
        )

    # =========================================================================
    # TOOL EXECUTION IMPLEMENTATIONS
    # =========================================================================

    def _execute_tool(self, function_name: str, args: Dict[str, Any]) -> str:
        """Execute an already-authorized tool call.

        The policy gate ran in _dispatch_tool_call() (or the user confirmed).
        All implementations live in access_os/actions.py — this is a thin
        delegate so there is exactly one copy of every OS action.
        """
        logger.info(f"Executing tool: {function_name} with args: {args}")
        return execute_tool_raw(
            function_name, args or {},
            status_callback=self._notify_status,
            notes_file=self.notes_file,
        )

    def request_confirmation(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Register a destructive action for user confirmation.

        Shared by the LLM path (_dispatch_tool_call) and the legacy regex
        path (VoiceCommandProcessor adapters). Returns the confirmation
        question to relay to the user. The user's next message is resolved
        in process().
        """
        args = args or {}
        self.pending_confirmation = (tool_name, args, time.time())
        question = confirmation_prompt(tool_name, args)
        self._audit(tool_name, args, "confirm_requested",
                    f"ACTION_REQUIRES_CONFIRMATION: {question}")
        return f"ACTION_REQUIRES_CONFIRMATION: {question}"

    def _audit(self, tool_name: str, args: Dict[str, Any], verdict: str, result: str):
        """Append one JSON line per tool call to the local audit log.

        The audit log is local-only (git-ignored) and never leaves the machine.
        It must never break execution — failures are swallowed deliberately.
        """
        try:
            safe_args = {k: (str(v)[:200]) for k, v in (args or {}).items()}
            entry = {
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "tool": tool_name,
                "args": safe_args,
                "verdict": verdict,
                "result": str(result)[:200],
            }
            with open(self.audit_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _dispatch_tool_call(self, function_name: str, args: Dict[str, Any]) -> str:
        """Policy-gated dispatch — the ONLY entry point for LLM tool calls.

        Every call passes through command_policy.check_tool_call() first:
          DENY    -> blocked, reason returned to the LLM (it can explain / offer
                     a safe alternative).
          CONFIRM -> not executed; the confirmation question is returned to the
                     LLM, which relays it to the user. The call is stored in
                     self.pending_confirmation and only runs if the user's next
                     message confirms (see process()).
          ALLOW   -> executed via _execute_tool().
        """
        args = args or {}
        verdict, reason = check_tool_call(function_name, args)

        if verdict == DENY:
            logger.warning(f"Blocked tool call: {function_name} ({reason})")
            result = f"Blocked for safety: {reason}"
            self._audit(function_name, args, "deny", result)
            return result

        if verdict == CONFIRM:
            return self.request_confirmation(function_name, args)

        result = self._execute_tool(function_name, args)
        self._audit(function_name, args, ALLOW, result)
        return result

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
                return execute_tool_raw("download_media", {"url_or_query": query, "media_type": media_type}, self._notify_status, self.notes_file)

        # 2. Open Application / Website requests
        if lowered.startswith("open ") or lowered.startswith("launch ") or lowered.startswith("go to "):
            target = lowered.replace("open ", "").replace("launch ", "").replace("go to ", "").strip()
            # If known website or dot in name
            if any(s in target for s in ["youtube", "google", "gmail", "github", "linkedin", "reddit", "netflix", "instagram", "facebook", "twitter", "whatsapp", "chatgpt"]) or "." in target:
                return execute_tool_raw("open_website", {"url_or_name": target}, self._notify_status, self.notes_file)
            return execute_tool_raw("open_application", {"app_name": target}, self._notify_status, self.notes_file)

        # 3. Write / Type text
        if lowered.startswith("write ") or lowered.startswith("type "):
            text = user_input
            for prefix in ["write that ", "write ", "type that ", "type "]:
                if lowered.startswith(prefix):
                    text = user_input[len(prefix):].strip()
                    break
            return execute_tool_raw("keyboard_mouse_action", {"action": "type_text", "value": text}, self._notify_status, self.notes_file)

        # 4. Search requests
        if "search for" in lowered or "search google for" in lowered or lowered.startswith("google "):
            for prefix in ["search google for ", "search for ", "google for ", "google "]:
                if prefix in lowered:
                    idx = lowered.find(prefix) + len(prefix)
                    query = user_input[idx:].strip()
                    return execute_tool_raw("web_search", {"query": query}, self._notify_status, self.notes_file)

        # 5. System commands
        if "screenshot" in lowered:
            return execute_tool_raw("system_control", {"action": "take_screenshot"}, self._notify_status, self.notes_file)
        # NOTE: lock_pc is destructive — not available in the offline fallback.
        # Use the gated path (LLM or regex engine) so confirmation applies.
        # NOTE: empty_recycle_bin is destructive — not available offline.
        if "battery" in lowered:
            return execute_tool_raw("system_control", {"action": "check_battery"}, self._notify_status, self.notes_file)
        if "volume up" in lowered or "increase volume" in lowered:
            return execute_tool_raw("system_control", {"action": "volume_up"}, self._notify_status, self.notes_file)
        if "volume down" in lowered or "decrease volume" in lowered:
            return execute_tool_raw("system_control", {"action": "volume_down"}, self._notify_status, self.notes_file)
        if "mute" in lowered:
            return execute_tool_raw("system_control", {"action": "mute"}, self._notify_status, self.notes_file)

        # 6. Notes
        if lowered.startswith("note that ") or lowered.startswith("take note ") or lowered.startswith("save note "):
            content = user_input
            for p in ["note that ", "take note ", "save note "]:
                if lowered.startswith(p):
                    content = user_input[len(p):].strip()
                    break
            return execute_tool_raw("manage_notes", {"action": "save", "content": content}, self._notify_status, self.notes_file)
        if "read my notes" in lowered or "show my notes" in lowered:
            return execute_tool_raw("manage_notes", {"action": "read"}, self._notify_status, self.notes_file)

        # Default fallback: search query
        return execute_tool_raw("web_search", {"query": user_input}, self._notify_status, self.notes_file)

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

        # 0. Resolve a pending destructive-action confirmation FIRST.
        #    A confirmed action bypasses the gate via _execute_tool() directly —
        #    it must NOT go back through _dispatch_tool_call(), or it would
        #    ask for confirmation again in an infinite loop.
        if self.pending_confirmation is not None:
            tool_name, c_args, ts = self.pending_confirmation
            self.pending_confirmation = None
            lowered = clean_input.lower().strip().rstrip(".!")
            if time.time() - ts > self.confirm_timeout:
                return "Confirmation timed out — action cancelled."
            if lowered in self.confirm_words:
                self._notify_status("Confirmed — executing...")
                result = self._execute_tool(tool_name, c_args)
                self._audit(tool_name, c_args, "confirmed", result)
                self.conversation_history.append({"role": "user", "content": clean_input})
                self.conversation_history.append({"role": "assistant", "content": result})
                return result
            return "Cancelled — I won't do that."

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
