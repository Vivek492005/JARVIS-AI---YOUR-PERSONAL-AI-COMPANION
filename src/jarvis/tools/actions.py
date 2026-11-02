"""
actions.py — Single home for every OS-manipulating action in JARVIS.

Phase C of the cleanup plan: both command engines (the LLM `AIAgent` and the
legacy regex `VoiceCommandProcessor`) used to implement the same ~15 OS
actions independently. Now every action lives here exactly once, as a plain
function. Both engines call into this module:

* `execute_tool_raw(tool_name, args, ...)` — direct execution, NO policy gate.
  Only for calls that already passed the gate (LLM path) or were explicitly
  confirmed by the user.
* `run_action(tool_name, args, ...)` — full pipeline: runs
  `command_policy.check_tool_call()` first and returns a
  `(verdict, result)` tuple. The legacy regex engine uses this so its
  destructive actions get the same confirm-before-destroy protection.

Tool names match the LLM tool definitions in ai_agent.py:
  open_application, open_website, web_search, download_media,
  system_control, keyboard_mouse_action, manage_notes, run_powershell_command
"""

import os
import sys
import json
import time
import logging
import datetime
import re
import subprocess
import webbrowser
import urllib.parse
from typing import Dict, Any, Tuple, Optional, Callable

logger = logging.getLogger(__name__)

try:
    from jarvis.policy.command_policy import check_tool_call, confirmation_prompt, ALLOW, CONFIRM, DENY
except ImportError:  # direct script execution
    from command_policy import check_tool_call, confirmation_prompt, ALLOW, CONFIRM, DENY


# ---------------------------------------------------------------------------
# Action implementations (moved verbatim from AIAgent, de-methodized:
# `self._notify_status` -> status_callback param, `self.notes_file` -> param)
# ---------------------------------------------------------------------------

# A-02: strict charset for the open_application() generic fallback.
# Excludes every cmd.exe metacharacter (& | < > ^ % ! " ') so a
# tool-arg-controlled name cannot break out of the `start` command line.
_APP_NAME_SAFE = re.compile(r"^[A-Za-z0-9_\-. ]{1,60}$")

def open_application(app_name: str, status_callback: Optional[Callable[[str], None]] = None) -> str:
    if status_callback:
        status_callback(f"Opening {app_name}...")
    lowered = (app_name or "").lower().strip()
    if not lowered:
        return "Please tell me which application to open."

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
        "taskmgr": ["taskmgr.exe"],
        "paint": ["mspaint.exe"],
        "mspaint": ["mspaint.exe"],
        "control panel": ["control.exe"],
        "control": ["control.exe"],
        "settings": ["start", "ms-settings:"],
        "spotify": ["start", "spotify:"],
        "word": ["start", "winword"],
        "excel": ["start", "excel"],
        "powerpoint": ["start", "powerpnt"],
    }

    for key, cmd in app_mappings.items():
        if key in lowered or lowered in key:
            try:
                # A-02: never shell=True here. Every mapping entry is
                # hardcoded, so a list-form spawn without a shell is
                # injection-proof. `start` is a cmd.exe builtin, hence
                # the explicit `cmd /c` for those entries.
                if cmd[0].lower() == "start":
                    subprocess.Popen(["cmd", "/c"] + cmd)
                else:
                    subprocess.Popen(cmd)
                return f"Successfully opened {app_name}."
            except Exception as e:
                logger.error(f"Failed to open mapped app {app_name}: {e}")

    # Generic Windows start — A-02: app_name is tool-arg-controlled, so it
    # must pass a strict charset check first. Without it, cmd.exe
    # metacharacters would allow command injection through the `start`
    # builtin's own argument parsing.
    name = (app_name or "").strip()
    if not _APP_NAME_SAFE.match(name):
        return (f"Could not launch {app_name}: the name contains unsupported "
                f"characters. Try the application's full name from the list.")
    try:
        subprocess.Popen(["cmd", "/c", "start", "", name])
        return f"Opened {app_name}."
    except Exception as e:
        logger.error(f"Failed to start app {app_name}: {e}")
        return f"Could not launch {app_name}: {e}"


def open_website(url_or_name: str, status_callback: Optional[Callable[[str], None]] = None) -> str:
    if status_callback:
        status_callback(f"Opening {url_or_name}...")
    url = (url_or_name or "").strip()
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
            return web_search(url, status_callback)

    webbrowser.open(url)
    return f"Opening {url_or_name}."


def web_search(query: str, status_callback: Optional[Callable[[str], None]] = None) -> str:
    if status_callback:
        status_callback(f"Searching web for '{query}'...")
    encoded = urllib.parse.quote_plus(query or "")
    webbrowser.open(f"https://www.google.com/search?q={encoded}")
    return f"Searching Google for {query}."


def download_media(url_or_query: str, media_type: str = "audio",
                   status_callback: Optional[Callable[[str], None]] = None) -> str:
    if status_callback:
        status_callback(f"Downloading {media_type} for '{url_or_query}'...")
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
        target = (url_or_query or "").strip()
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


def system_control(action: str, status_callback: Optional[Callable[[str], None]] = None) -> str:
    if status_callback:
        status_callback(f"Executing system control: {action}...")
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
            # Task 1.4: no os.system — fixed argv, no shell.
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"],
                           check=False)
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


# Task 1.4: typing into (or Enter-ing inside) a terminal, the Run dialog,
# regedit, taskmgr, … is the classic prompt-injection kill chain
# (win+r -> type -> enter). These foreground processes are never typed into.
_TERMINAL_PROCESSES = frozenset({
    "cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe",
    "wt.exe", "conhost.exe",
    "regedit.exe", "taskmgr.exe",
})


def get_foreground_process() -> Optional[str]:
    """Process name (lowercase exe) of the foreground window.

    Windows only; returns None when it cannot be determined (non-Windows,
    or the Win32 query failed) — the guard then passes open.
    """
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        hproc = kernel32.OpenProcess(0x1000, False, pid.value)  # QUERY_LIMITED_INFORMATION
        if not hproc:
            return None
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = wintypes.DWORD(260)
            if kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value).lower() or None
        finally:
            kernel32.CloseHandle(hproc)
    except Exception:
        pass
    return None


def _foreground_guard() -> Optional[str]:
    """Returns a block message if the foreground window is a terminal etc."""
    fg = get_foreground_process()
    if fg in _TERMINAL_PROCESSES:
        return (f"Blocked for safety: the foreground window is {fg} — "
                f"typing into terminals is disabled (Task 1.4).")
    return None


def keyboard_mouse_action(action: str, value: str,
                          status_callback: Optional[Callable[[str], None]] = None) -> str:
    if status_callback:
        status_callback(f"Performing {action}...")
    # Task 1.4: foreground-window guard runs before any keystroke.
    if action in ("type_text", "press_key", "press_hotkey"):
        blocked = _foreground_guard()
        if blocked:
            logger.warning(f"Foreground guard blocked {action}: {blocked}")
            return blocked
    try:
        import pyautogui
        import pyperclip

        if action == "type_text":
            pyperclip.copy(value)
            pyautogui.hotkey("ctrl", "v")
            return f"Typed: '{value}'"
        elif action == "press_hotkey":
            keys = [k.strip().lower() for k in (value or "").split("+")]
            pyautogui.hotkey(*keys)
            return f"Pressed hotkey {value}."
        elif action == "press_key":
            pyautogui.press((value or "").lower().strip())
            return f"Pressed key {value}."
        return f"Unknown keyboard action: {action}"
    except Exception as e:
        logger.error(f"Keyboard/mouse action error: {e}")
        return f"Action failed: {e}"


def manage_notes(action: str, content: Optional[str] = None, notes_file: str = "notes.txt",
                 status_callback: Optional[Callable[[str], None]] = None) -> str:
    # A-06: notes_file is dispatcher-provided and must stay a plain filename
    # inside the working directory — never a path (no traversal).
    if (os.path.basename(notes_file) != notes_file or ".." in notes_file
            or os.path.isabs(notes_file)):
        return "Invalid notes file."
    if status_callback:
        status_callback("Managing notes...")
    if action == "save":
        if not content:
            return "No note content provided."
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {content}\n")
        return f"Note saved: {content}"
    elif action == "read":
        if not os.path.exists(notes_file):
            return "You do not have any notes saved yet."
        with open(notes_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        if not lines:
            return "Your notes file is empty."
        recent = lines[-5:]
        return "Here are your recent notes: " + " | ".join(recent)
    elif action == "clear":
        if os.path.exists(notes_file):
            os.remove(notes_file)
        return "Cleared all your notes."
    return f"Unknown note action: {action}"


def run_powershell_command(command: str,
                           status_callback: Optional[Callable[[str], None]] = None) -> str:
    if status_callback:
        status_callback(f"Running command: {command}...")
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command or ""],
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


# ---------------------------------------------------------------------------
# Tool registry wiring (Task 1.2). The registry is the single authority on
# which tools exist, their arg schemas and their risk tiers. Handlers stay
# here — the single home for implementations (Phase C).
# ---------------------------------------------------------------------------

# Task 1.4.3: allowlisted shell-style commands. The LLM only picks a KEY —
# it never supplies a command string. Fixed argv, shell=False, timeout.
_ALLOWED_COMMANDS = {
    "ipconfig": ["ipconfig"],
    "disk_free": ["powershell", "-NoProfile",
                  "-Command", "Get-PSDrive -PSProvider FileSystem"],
}


def run_command(command_key: str,
                status_callback: Optional[Callable[[str], None]] = None) -> str:
    """Run one allowlisted diagnostic command template (read-only)."""
    argv = _ALLOWED_COMMANDS.get(command_key or "")
    if argv is None:
        return (f"Unknown command '{command_key}'. "
                f"Available: {', '.join(sorted(_ALLOWED_COMMANDS))}.")
    if status_callback:
        status_callback(f"Running {command_key}...")
    try:
        out = subprocess.run(argv, shell=False, capture_output=True,
                             text=True, timeout=10)
        body = (out.stdout or "").strip()[:2000]
        return body if body else "(no output)"
    except Exception as e:
        logger.error(f"run_command {command_key} failed: {e}")
        return f"Command failed: {e}"


def _register_tools():
    # Idempotent: skills loaded first win; this fills any gaps.
    from jarvis.tools.registry import REGISTRY as _REG
    from jarvis.tools.registry import (
        DownloadMediaParams,
        KeyboardMouseParams,
        ManageNotesParams,
        OpenApplicationParams,
        OpenWebsiteParams,
        Risk,
        RunCommandParams,
        RunPowershellParams,
        SystemControlParams,
        WebSearchParams,
        tool,
        ToolSpec,
    )

    def _reg(spec):
        if spec.name in _REG:
            return _REG.get(spec.name)
        return tool(spec)

    def _sub(name, risk, description, params):
        # Sub-action specs share the base tool's handler; resolve() picks the
        # right risk tier from the `action` argument.
        base = _BASE_HANDLERS[name.split(".")[0]]
        _reg(ToolSpec(name=name, description=description, params=params,
                      risk=risk, handler=base))

    _reg(ToolSpec(
        name="open_application", risk=Risk.REVERSIBLE,
        description="Opens or launches an application or program installed on "
                    "the Windows PC (e.g. Chrome, Notepad, VS Code, "
                    "Calculator, Spotify, WhatsApp, Word, Excel, File "
                    "Explorer, Command Prompt, etc.).",
        params=OpenApplicationParams,
        handler=_BASE_HANDLERS["open_application"]))
    _reg(ToolSpec(
        name="open_website", risk=Risk.REVERSIBLE,
        description="Opens a specific website or web portal in the user's "
                    "default browser.",
        params=OpenWebsiteParams,
        handler=_BASE_HANDLERS["open_website"],
        scopes=frozenset({"network"})))
    _reg(ToolSpec(
        name="web_search", risk=Risk.READ,
        description="Searches Google or the web for real-time information, "
                    "answers, queries, or news requested by the user.",
        params=WebSearchParams,
        handler=_BASE_HANDLERS["web_search"],
        carries_external_data=True,
        scopes=frozenset({"network"})))
    _reg(ToolSpec(
        name="download_media", risk=Risk.REVERSIBLE,
        description="Downloads video or audio from YouTube or any media URL, "
                    "or searches and downloads the requested song or video "
                    "using yt-dlp.",
        params=DownloadMediaParams,
        handler=_BASE_HANDLERS["download_media"],
        scopes=frozenset({"network"})))
    # system_control: per-action risk tiers; base is SYSTEM (fail-closed).
    _reg(ToolSpec(
        name="system_control", risk=Risk.SYSTEM,
        description="Controls Windows OS system functions: volume "
                    "adjustments, mute, screenshot capture, lock workstation, "
                    "empty recycle bin, battery check.",
        params=SystemControlParams,
        handler=_BASE_HANDLERS["system_control"]))
    _sub("system_control.take_screenshot", Risk.READ,
         "Capture a screenshot.", SystemControlParams)
    _sub("system_control.check_battery", Risk.READ,
         "Report battery status.", SystemControlParams)
    for _vol in ("volume_up", "volume_down", "mute", "unmute"):
        _sub(f"system_control.{_vol}", Risk.REVERSIBLE,
             f"System {_vol.replace('_', ' ')}.", SystemControlParams)
    _sub("system_control.empty_recycle_bin", Risk.DESTRUCTIVE,
         "Permanently empty the Recycle Bin.", SystemControlParams)
    _sub("system_control.lock_pc", Risk.SYSTEM,
         "Lock the workstation.", SystemControlParams)
    _reg(ToolSpec(
        # SYSTEM until the Task 1.4 foreground-window guard lands.
        name="keyboard_mouse_action", risk=Risk.SYSTEM,
        description="Types text or fires a hotkey. Blocked hotkeys "
                    "(alt+f4, win+r, …) are denied by the policy gate; "
                    "typing into terminals is blocked by the foreground "
                    "guard.",
        params=KeyboardMouseParams,
        handler=_BASE_HANDLERS["keyboard_mouse_action"]))
    # Task 1.4.2: per-action tiers (the foreground guard in the executor is
    # the last line of defense even when a tier auto-allows).
    _sub("keyboard_mouse_action.type_text", Risk.REVERSIBLE,
         "Type text into the foreground window (never a terminal).",
         KeyboardMouseParams)
    _sub("keyboard_mouse_action.press_key", Risk.REVERSIBLE,
         "Press a single key.", KeyboardMouseParams)
    _sub("keyboard_mouse_action.press_hotkey_safe", Risk.REVERSIBLE,
         "Press an allowlisted hotkey (ctrl+c/v/x/z/s/f/a/t/w/r, win+d).",
         KeyboardMouseParams)
    _sub("keyboard_mouse_action.press_hotkey_other", Risk.SYSTEM,
         "Press a non-allowlisted hotkey (always confirmed; blocked ones "
         "are denied outright).", KeyboardMouseParams)
    _reg(ToolSpec(
        name="manage_notes", risk=Risk.REVERSIBLE,
        description="Save, read, or clear the user's persistent notes.",
        params=ManageNotesParams,
        handler=_BASE_HANDLERS["manage_notes"],
        carries_external_data=True))
    _sub("manage_notes.clear", Risk.DESTRUCTIVE,
         "Permanently clear all notes.", ManageNotesParams)
    _reg(ToolSpec(
        name="run_powershell_command", risk=Risk.SYSTEM,
        description="Runs a read-only PowerShell command (validated against "
                    "the allowlist; destructive cmdlets are denied).",
        params=RunPowershellParams,
        handler=_BASE_HANDLERS["run_powershell_command"],
        carries_external_data=True))
    _reg(ToolSpec(
        # Task 1.4.3: fixed read-only templates; the LLM picks only a key.
        name="run_command", risk=Risk.READ,
        description="Runs one allowlisted read-only diagnostic template "
                    "(ipconfig, disk_free). No arbitrary commands.",
        params=RunCommandParams,
        handler=_BASE_HANDLERS["run_command"],
        carries_external_data=True))

    # Phase 5: perception/control tools register through the same gate.
    from jarvis.perception.tools import register_perception_tools
    register_perception_tools()

    # Phase 6: integrations (MCP, PIM, scheduler, heartbeat) — same gate.
    from jarvis.integrations.tools import register_integration_tools
    register_integration_tools()


_BASE_HANDLERS = {
    "open_application": lambda args, cb, nf: open_application(args.get("app_name", ""), cb),
    "open_website": lambda args, cb, nf: open_website(args.get("url_or_name", ""), cb),
    "web_search": lambda args, cb, nf: web_search(args.get("query", ""), cb),
    "download_media": lambda args, cb, nf: download_media(
        args.get("url_or_query", ""), args.get("media_type", "audio"), cb),
    "system_control": lambda args, cb, nf: system_control(args.get("action", ""), cb),
    "keyboard_mouse_action": lambda args, cb, nf: keyboard_mouse_action(
        args.get("action", ""), args.get("value", ""), cb),
    # A-06: notes_file is dispatcher-provided, never part of the tool schema.
    "manage_notes": lambda args, cb, nf: manage_notes(
        args.get("action", ""), args.get("content", None), nf, cb),
    "run_powershell_command": lambda args, cb, nf: run_powershell_command(
        args.get("command", ""), cb),
    "run_command": lambda args, cb, nf: run_command(
        args.get("command_key", ""), cb),
}

_register_tools()


def execute_tool_raw(tool_name: str, args: Dict[str, Any],
                     status_callback: Optional[Callable[[str], None]] = None,
                     notes_file: str = "notes.txt") -> str:
    """Execute a tool with NO policy gate.

    Only call this for tool calls that already passed check_tool_call()
    (the AIAgent._dispatch_tool_call path) or were explicitly confirmed by
    the user. Anything else must go through run_action().

    Task 1.2: the tool MUST be registered and its args MUST validate
    against the spec's pydantic model — otherwise the call is rejected.
    """
    from jarvis.tools.registry import resolve
    from pydantic import ValidationError

    spec = resolve(tool_name, args or {})
    if spec is None:
        return f"Tool {tool_name} is not recognized."
    try:
        validated = spec.params(**(args or {}))
    except ValidationError as e:
        first = e.errors()[0]
        loc = ".".join(str(p) for p in first["loc"])
        return f"Invalid arguments for {tool_name}: {loc}: {first['msg']}"
    return spec.handler(validated.model_dump(), status_callback, notes_file)


def _audit_log(tool_name: str, args: Dict[str, Any], verdict: str, result: str,
               audit_file: str = "jarvis_audit.log",
               latency_ms: Optional[float] = None):
    """Append one JSON line per tool call (Task 1.7).

    All audit output now goes through AuditLogger -> audit/YYYY-MM-DD.jsonl
    (redacted). The legacy ``audit_file`` parameter is accepted for
    backward compatibility but no longer used.
    """
    from jarvis.policy.audit import AuditLogger
    try:
        AuditLogger().log(tool_name, args, verdict,
                          reason=str(result)[:300], latency_ms=latency_ms)
    except Exception:
        pass


def _engine_decision(tool_name: str, args: Dict[str, Any],
                   ctx=None) -> Tuple[str, str]:
    """Task 1.3: the single decision point — registry risk tier × arg rules.

    Returns ("allow"/"confirm"/"deny", reason). The level comes from
    Settings (safety.autonomy_level); ctx carries taint/rate-limit state.
    """
    from jarvis.policy import decide_tool_call
    try:
        from jarvis.core.config import get_settings
        level = get_settings().safety.autonomy_level
    except Exception:
        level = 1
    # Task 8.3: when the caller didn't supply a context, build one from the
    # effective settings so --safe / offline mode apply to every entry point.
    if ctx is None:
        from jarvis.policy import context_from_settings
        ctx = context_from_settings()
    decision, reason = decide_tool_call(tool_name, args, ctx,
                                        level)
    return ({"ALLOW": ALLOW, "CONFIRM": CONFIRM, "DENY": DENY}[decision.name],
            reason)


def run_action(tool_name: str, args: Dict[str, Any],
               status_callback: Optional[Callable[[str], None]] = None,
               notes_file: str = "notes.txt",
               audit_file: str = "jarvis_audit.log",
               ctx=None) -> Tuple[str, str]:
    """Policy-gated execution for the legacy regex engine (and any other
    non-LLM caller). Returns (verdict, result) where verdict is one of
    "allow" / "confirm" / "deny".

    Every call is written to the audit log. On "confirm", the caller must ask
    the user and only call execute_tool_raw() after explicit confirmation —
    or hand the tool call to AIAgent.request_confirmation(), which owns the
    confirmation state.
    """
    args = args or {}
    verdict, reason = _engine_decision(tool_name, args, ctx)
    if verdict == DENY:
        logger.warning(f"Blocked tool call: {tool_name} ({reason})")
        result = f"Blocked for safety: {reason}"
        _audit_log(tool_name, args, DENY, result, audit_file)
        return (DENY, result)
    if verdict == CONFIRM:
        result = f"ACTION_REQUIRES_CONFIRMATION: {confirmation_prompt(tool_name, args)}"
        _audit_log(tool_name, args, "confirm_requested", result, audit_file)
        return (CONFIRM, result)
    _t0 = time.time()
    result = execute_tool_raw(tool_name, args, status_callback, notes_file)
    latency_ms = (time.time() - _t0) * 1000.0
    _audit_log(tool_name, args, ALLOW, result, audit_file,
               latency_ms=latency_ms)
    return (ALLOW, result)
