"""
JARVIS - Enhanced Voice Interface & Natural Language Command Processor
Handles speech recognition, text-to-speech, and 100+ voice commands.
"""

import os
import re
import sys
import time
import json
import queue
import random
import logging
import datetime
import threading
import subprocess
import webbrowser
import urllib.parse
import tempfile
import ctypes
import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable, Dict, Any, List, Tuple

import speech_recognition as sr
import pyttsx3
import pyautogui
import pyperclip
from fuzzywuzzy import fuzz

# Configure pyautogui safety
pyautogui.FAILSAFE = False
logger = logging.getLogger(__name__)

# Import DeepSeek intelligent AI Agent
try:
    from .ai_agent import AIAgent
except ImportError:
    from access_os.ai_agent import AIAgent


class CommandType(Enum):
    """Categories of voice commands."""
    SYSTEM = auto()
    APPLICATION = auto()
    NAVIGATION = auto()
    MEDIA = auto()
    WEB = auto()
    UTILITY = auto()
    EDITING = auto()
    AI = auto()
    FILE = auto()
    CUSTOM = auto()


@dataclass
class VoiceCommand:
    """Represents a recognized voice command."""
    text: str
    confidence: float = 1.0
    command_type: CommandType = CommandType.CUSTOM
    is_final: bool = True
    timestamp: float = field(default_factory=time.time)
    matched_action: Optional[str] = None
    response: Optional[str] = None


class VoiceCommandProcessor:
    """Comprehensive voice command processor supporting 100+ actions."""

    def __init__(self, notes_file: str = "notes.txt"):
        self.notes_file = notes_file
        self.last_response = "I haven't said anything yet."
        self.history = []
        self._init_command_registry()

    def _init_command_registry(self):
        """Initialize all command patterns, handlers, and responses."""
        self.commands = [
            # ==========================================
            # 1. Popular Websites & Web Portals (25+)
            # ==========================================
            {
                "id": "open_youtube",
                "patterns": [r"^(open|go to|launch) youtube$", r"^youtube$"],
                "action": lambda m: self._open_url("https://www.youtube.com", "Opening YouTube"),
                "type": CommandType.WEB
            },
            {
                "id": "open_linkedin",
                "patterns": [r"^(open|go to|launch) linkedin$", r"^linkedin$"],
                "action": lambda m: self._open_url("https://www.linkedin.com", "Opening LinkedIn"),
                "type": CommandType.WEB
            },
            {
                "id": "open_gmail",
                "patterns": [r"^(open|go to|launch|check) (gmail|email|mail)$", r"^gmail$"],
                "action": lambda m: self._open_url("https://mail.google.com", "Opening Gmail"),
                "type": CommandType.WEB
            },
            {
                "id": "open_github",
                "patterns": [r"^(open|go to|launch) github$", r"^github$"],
                "action": lambda m: self._open_url("https://github.com", "Opening GitHub"),
                "type": CommandType.WEB
            },
            {
                "id": "open_google",
                "patterns": [r"^(open|go to|launch) google$", r"^google$"],
                "action": lambda m: self._open_url("https://www.google.com", "Opening Google"),
                "type": CommandType.WEB
            },
            {
                "id": "open_whatsapp",
                "patterns": [r"^(open|go to|launch) (whatsapp|whatsapp web)$", r"^whatsapp$"],
                "action": lambda m: self._open_url("https://web.whatsapp.com", "Opening WhatsApp Web"),
                "type": CommandType.WEB
            },
            {
                "id": "open_chatgpt",
                "patterns": [r"^(open|go to|launch) (chat gpt|chatgpt|openai)$"],
                "action": lambda m: self._open_url("https://chat.openai.com", "Opening ChatGPT"),
                "type": CommandType.WEB
            },
            {
                "id": "open_twitter",
                "patterns": [r"^(open|go to|launch) (twitter|x)$", r"^twitter$"],
                "action": lambda m: self._open_url("https://twitter.com", "Opening Twitter"),
                "type": CommandType.WEB
            },
            {
                "id": "open_instagram",
                "patterns": [r"^(open|go to|launch) instagram$", r"^instagram$"],
                "action": lambda m: self._open_url("https://www.instagram.com", "Opening Instagram"),
                "type": CommandType.WEB
            },
            {
                "id": "open_facebook",
                "patterns": [r"^(open|go to|launch) facebook$", r"^facebook$"],
                "action": lambda m: self._open_url("https://www.facebook.com", "Opening Facebook"),
                "type": CommandType.WEB
            },
            {
                "id": "open_reddit",
                "patterns": [r"^(open|go to|launch) reddit$", r"^reddit$"],
                "action": lambda m: self._open_url("https://www.reddit.com", "Opening Reddit"),
                "type": CommandType.WEB
            },
            {
                "id": "open_netflix",
                "patterns": [r"^(open|go to|launch) netflix$", r"^netflix$"],
                "action": lambda m: self._open_url("https://www.netflix.com", "Opening Netflix"),
                "type": CommandType.WEB
            },
            {
                "id": "open_spotify",
                "patterns": [r"^(open|go to|launch) spotify$", r"^spotify$"],
                "action": lambda m: self._open_url("https://open.spotify.com", "Opening Spotify"),
                "type": CommandType.WEB
            },
            {
                "id": "open_amazon",
                "patterns": [r"^(open|go to|launch) amazon$", r"^amazon$"],
                "action": lambda m: self._open_url("https://www.amazon.com", "Opening Amazon"),
                "type": CommandType.WEB
            },
            {
                "id": "open_stackoverflow",
                "patterns": [r"^(open|go to|launch) stack ?overflow$"],
                "action": lambda m: self._open_url("https://stackoverflow.com", "Opening Stack Overflow"),
                "type": CommandType.WEB
            },
            {
                "id": "open_maps",
                "patterns": [r"^(open|go to|launch) (google maps|maps)$"],
                "action": lambda m: self._open_url("https://maps.google.com", "Opening Google Maps"),
                "type": CommandType.WEB
            },
            {
                "id": "open_drive",
                "patterns": [r"^(open|go to|launch) (google drive|drive)$"],
                "action": lambda m: self._open_url("https://drive.google.com", "Opening Google Drive"),
                "type": CommandType.WEB
            },
            {
                "id": "open_docs",
                "patterns": [r"^(open|go to|launch) (google docs|docs)$"],
                "action": lambda m: self._open_url("https://docs.google.com", "Opening Google Docs"),
                "type": CommandType.WEB
            },
            {
                "id": "open_calendar",
                "patterns": [r"^(open|go to|launch) (google calendar|calendar)$"],
                "action": lambda m: self._open_url("https://calendar.google.com", "Opening Google Calendar"),
                "type": CommandType.WEB
            },
            {
                "id": "open_news",
                "patterns": [r"^(open|show me|check) (the news|google news|news)$"],
                "action": lambda m: self._open_url("https://news.google.com", "Opening Google News"),
                "type": CommandType.WEB
            },
            {
                "id": "open_wikipedia",
                "patterns": [r"^(open|go to|launch) wikipedia$", r"^wikipedia$"],
                "action": lambda m: self._open_url("https://www.wikipedia.org", "Opening Wikipedia"),
                "type": CommandType.WEB
            },
            {
                "id": "open_leetcode",
                "patterns": [r"^(open|go to|launch) leetcode$", r"^leetcode$"],
                "action": lambda m: self._open_url("https://leetcode.com", "Opening LeetCode"),
                "type": CommandType.WEB
            },
            {
                "id": "open_discord",
                "patterns": [r"^(open|go to|launch) discord$", r"^discord$"],
                "action": lambda m: self._open_url("https://discord.com/app", "Opening Discord"),
                "type": CommandType.WEB
            },
            {
                "id": "open_medium",
                "patterns": [r"^(open|go to|launch) medium$", r"^medium$"],
                "action": lambda m: self._open_url("https://medium.com", "Opening Medium"),
                "type": CommandType.WEB
            },
            {
                "id": "open_pinterest",
                "patterns": [r"^(open|go to|launch) pinterest$", r"^pinterest$"],
                "action": lambda m: self._open_url("https://www.pinterest.com", "Opening Pinterest"),
                "type": CommandType.WEB
            },

            # ==========================================
            # 2. YouTube & Media Suite (20+)
            # ==========================================
            {
                "id": "play_youtube",
                "patterns": [
                    r"^play (.+) (on|in) youtube$",
                    r"^play (.+) youtube$",
                    r"^search youtube for (.+)$",
                    r"^youtube search (.+)$"
                ],
                "action": self._action_play_youtube,
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_pause",
                "patterns": [
                    r"^(youtube )?(pause|resume|play video)$",
                    r"^(pause|resume) (playback|video|music)$",
                    r"^(pause|resume)$"
                ],
                "action": lambda m: self._press_key("k", "Toggled YouTube video playback"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_stop",
                "patterns": [r"^stop (playback|music|video|song|media)$"],
                "action": lambda m: self._press_key("stop", "Stopping playback"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_fullscreen",
                "patterns": [
                    r"^(youtube )?(fullscreen|full screen)$",
                    r"^(toggle |go to )?(full ?screen|fullscreen)$"
                ],
                "action": lambda m: self._press_key("f", "Toggled fullscreen"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_theater",
                "patterns": [r"^(youtube )?(theater mode|theatre mode)$"],
                "action": lambda m: self._press_key("t", "Toggled theater mode"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_miniplayer",
                "patterns": [r"^(youtube )?(mini player|miniplayer)$"],
                "action": lambda m: self._press_key("i", "Toggled miniplayer"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_mute",
                "patterns": [
                    r"^(youtube )?(mute|unmute)( video| sound)?$",
                    r"^(mute|unmute) youtube$"
                ],
                "action": lambda m: self._press_key("m", "Toggled video mute"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_captions",
                "patterns": [r"^(youtube )?(captions|subtitles|toggle captions|toggle subtitles)$"],
                "action": lambda m: self._press_key("c", "Toggled subtitles"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_skip_forward",
                "patterns": [r"^(youtube )?(skip 10 seconds|forward|skip forward|fast forward)$"],
                "action": lambda m: self._press_key("l", "Skipped 10 seconds forward"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_rewind",
                "patterns": [r"^(youtube )?(rewind|back 10 seconds|skip back|rewind 10 seconds)$"],
                "action": lambda m: self._press_key("j", "Rewound 10 seconds"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_speed_up",
                "patterns": [r"^(youtube )?(speed up|faster video|increase playback speed)$"],
                "action": lambda m: self._hotkey(["shift", "."], "Increased video speed"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_slow_down",
                "patterns": [r"^(youtube )?(slow down|slower video|decrease playback speed)$"],
                "action": lambda m: self._hotkey(["shift", ","], "Decreased video speed"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_restart",
                "patterns": [r"^(youtube )?(restart video|start of video|replay video)$"],
                "action": lambda m: self._press_key("0", "Restarted video from beginning"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_next",
                "patterns": [r"^(youtube )?(next video|next track|next song|skip video)$", r"^next (track|song)$"],
                "action": lambda m: self._hotkey(["shift", "n"], "Playing next video"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_prev",
                "patterns": [r"^(youtube )?(previous video|prev video|previous track)$", r"^previous (track|song)$"],
                "action": lambda m: self._hotkey(["shift", "p"], "Playing previous video"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_subscriptions",
                "patterns": [r"^(open |go to )?youtube (subscriptions|subs)$"],
                "action": lambda m: self._open_url("https://www.youtube.com/feed/subscriptions", "Opening YouTube Subscriptions"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_history",
                "patterns": [r"^(open |go to )?youtube history$"],
                "action": lambda m: self._open_url("https://www.youtube.com/feed/history", "Opening YouTube History"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_trending",
                "patterns": [r"^(open |go to )?youtube trending$"],
                "action": lambda m: self._open_url("https://www.youtube.com/feed/trending", "Opening YouTube Trending"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_library",
                "patterns": [r"^(open |go to )?youtube (library|watch later)$"],
                "action": lambda m: self._open_url("https://www.youtube.com/playlist?list=WL", "Opening YouTube Watch Later"),
                "type": CommandType.MEDIA
            },
            {
                "id": "youtube_shorts",
                "patterns": [r"^(open |go to )?youtube shorts$"],
                "action": lambda m: self._open_url("https://www.youtube.com/shorts", "Opening YouTube Shorts"),
                "type": CommandType.MEDIA
            },
            {
                "id": "download_youtube_video",
                "patterns": [
                    r"^download (this|current|the)? ?(video|song|youtube video)( (.+))?$",
                    r"^download (.+) (from|on) youtube$"
                ],
                "action": lambda m: self._action_download_youtube(m, audio_only=False),
                "type": CommandType.MEDIA
            },
            {
                "id": "download_youtube_audio",
                "patterns": [
                    r"^download (this|current|the)? ?(mp3|audio)( (.+))?$",
                    r"^download audio of (.+)$"
                ],
                "action": lambda m: self._action_download_youtube(m, audio_only=True),
                "type": CommandType.MEDIA
            },

            # ==========================================
            # 3. System Volume & Audio Control (10+)
            # ==========================================
            {
                "id": "volume_up",
                "patterns": [r"^(volume up|increase volume|louder|raise volume)$", r"^turn up the volume$"],
                "action": lambda m: self._change_volume(up=True, steps=5),
                "type": CommandType.SYSTEM
            },
            {
                "id": "volume_down",
                "patterns": [r"^(volume down|decrease volume|lower volume|softer)$", r"^turn down the volume$"],
                "action": lambda m: self._change_volume(up=False, steps=5),
                "type": CommandType.SYSTEM
            },
            {
                "id": "volume_max",
                "patterns": [r"^(volume max|maximum volume|volume to 100|full volume)$"],
                "action": lambda m: self._change_volume(up=True, steps=25, msg="Volume set to maximum"),
                "type": CommandType.SYSTEM
            },
            {
                "id": "volume_min",
                "patterns": [r"^(volume min|minimum volume|lowest volume)$"],
                "action": lambda m: self._change_volume(up=False, steps=25, msg="Volume set to minimum"),
                "type": CommandType.SYSTEM
            },
            {
                "id": "volume_mute",
                "patterns": [r"^(mute|unmute|mute sound|mute volume|toggle mute)$"],
                "action": lambda m: self._press_key("volumemute", "Mute toggled"),
                "type": CommandType.SYSTEM
            },

            # ==========================================
            # 4. Windows Desktop & Applications (16+)
            # ==========================================
            {
                "id": "open_notepad",
                "patterns": [r"^(open|launch) notepad$", r"^notepad$"],
                "action": lambda m: self._launch_app("notepad", "Opening Notepad"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "open_calculator",
                "patterns": [r"^(open|launch) calculator$", r"^calculator$"],
                "action": lambda m: self._launch_app("calc", "Opening Calculator"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "open_paint",
                "patterns": [r"^(open|launch) (paint|mspaint)$"],
                "action": lambda m: self._launch_app("mspaint", "Opening Paint"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "open_explorer",
                "patterns": [r"^(open|launch) (explorer|file explorer|files|this pc|my computer)$"],
                "action": lambda m: self._launch_app("explorer", "Opening File Explorer"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "open_cmd",
                "patterns": [r"^(open|launch) (command prompt|cmd|terminal)$"],
                "action": lambda m: self._launch_app("cmd", "Opening Command Prompt"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "open_powershell",
                "patterns": [r"^(open|launch) powershell$"],
                "action": lambda m: self._launch_app("powershell", "Opening PowerShell"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "open_task_manager",
                "patterns": [r"^(open|launch) task manager$"],
                "action": lambda m: self._launch_app("taskmgr", "Opening Task Manager"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "open_settings",
                "patterns": [r"^(open|launch) (settings|windows settings)$"],
                "action": lambda m: self._launch_app("start ms-settings:", "Opening Windows Settings"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "open_control_panel",
                "patterns": [r"^(open|launch) control panel$"],
                "action": lambda m: self._launch_app("control", "Opening Control Panel"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "open_chrome",
                "patterns": [r"^(open|launch) (chrome|google chrome)$"],
                "action": lambda m: self._launch_app("start chrome", "Opening Google Chrome"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "open_edge",
                "patterns": [r"^(open|launch) (edge|microsoft edge)$"],
                "action": lambda m: self._launch_app("start msedge", "Opening Microsoft Edge"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "open_vscode",
                "patterns": [r"^(open|launch) (vs code|vscode|code)$"],
                "action": lambda m: self._launch_app("code", "Opening Visual Studio Code"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "open_word",
                "patterns": [r"^(open|launch) (word|microsoft word)$"],
                "action": lambda m: self._launch_app("start winword", "Opening Microsoft Word"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "open_excel",
                "patterns": [r"^(open|launch) (excel|microsoft excel)$"],
                "action": lambda m: self._launch_app("start excel", "Opening Microsoft Excel"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "open_powerpoint",
                "patterns": [r"^(open|launch) (powerpoint|power point)$"],
                "action": lambda m: self._launch_app("start powerpnt", "Opening PowerPoint"),
                "type": CommandType.APPLICATION
            },
            {
                "id": "close_window",
                "patterns": [r"^(close window|close app|close this|close application|exit window)$"],
                "action": lambda m: self._hotkey(["alt", "f4"], "Closing active window"),
                "type": CommandType.APPLICATION
            },

            # ==========================================
            # 5. Window & Desktop Management (12+)
            # ==========================================
            {
                "id": "minimize_window",
                "patterns": [r"^(minimize|minimize window|minimize this)$"],
                "action": lambda m: self._hotkey(["win", "down"], "Window minimized"),
                "type": CommandType.SYSTEM
            },
            {
                "id": "maximize_window",
                "patterns": [r"^(maximize|maximize window|maximize this)$"],
                "action": lambda m: self._hotkey(["win", "up"], "Window maximized"),
                "type": CommandType.SYSTEM
            },
            {
                "id": "show_desktop",
                "patterns": [r"^(show desktop|go to desktop|minimize all)$"],
                "action": lambda m: self._hotkey(["win", "d"], "Showing desktop"),
                "type": CommandType.SYSTEM
            },
            {
                "id": "switch_window",
                "patterns": [r"^(switch window|switch app|next window)$"],
                "action": lambda m: self._hotkey(["alt", "tab"], "Switching window"),
                "type": CommandType.SYSTEM
            },
            {
                "id": "task_view",
                "patterns": [r"^(task view|open task view)$"],
                "action": lambda m: self._hotkey(["win", "tab"], "Opening Task View"),
                "type": CommandType.SYSTEM
            },
            {
                "id": "lock_computer",
                "patterns": [r"^(lock computer|lock pc|lock screen|lock windows)$"],
                "action": lambda m: self._action_lock_pc(),
                "type": CommandType.SYSTEM
            },
            {
                "id": "take_screenshot",
                "patterns": [r"^(take a screenshot|capture screen|screenshot|take screenshot)$"],
                "action": lambda m: self._action_take_screenshot(),
                "type": CommandType.SYSTEM
            },
            {
                "id": "open_action_center",
                "patterns": [r"^(open action center|open notifications|show notifications)$"],
                "action": lambda m: self._hotkey(["win", "a"], "Opening Action Center"),
                "type": CommandType.SYSTEM
            },
            {
                "id": "open_clipboard",
                "patterns": [r"^(open clipboard|show clipboard|clipboard history)$"],
                "action": lambda m: self._hotkey(["win", "v"], "Opening Clipboard history"),
                "type": CommandType.SYSTEM
            },
            {
                "id": "empty_recycle_bin",
                "patterns": [r"^(empty recycle bin|clean recycle bin)$"],
                "action": lambda m: self._action_empty_recycle_bin(),
                "type": CommandType.SYSTEM
            },

            # ==========================================
            # 6. Browser Tabs & Page Navigation (15+)
            # ==========================================
            {
                "id": "new_tab",
                "patterns": [r"^(new tab|open new tab)$"],
                "action": lambda m: self._hotkey(["ctrl", "t"], "Opened new tab"),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "close_tab",
                "patterns": [r"^(close tab|close current tab)$"],
                "action": lambda m: self._hotkey(["ctrl", "w"], "Closed tab"),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "reopen_tab",
                "patterns": [r"^(reopen tab|undo close tab|restore tab)$"],
                "action": lambda m: self._hotkey(["ctrl", "shift", "t"], "Reopened closed tab"),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "next_tab",
                "patterns": [r"^(next tab|switch to next tab)$"],
                "action": lambda m: self._hotkey(["ctrl", "pagedown"], "Switched to next tab"),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "previous_tab",
                "patterns": [r"^(previous tab|prev tab|switch to previous tab)$"],
                "action": lambda m: self._hotkey(["ctrl", "pageup"], "Switched to previous tab"),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "refresh_page",
                "patterns": [r"^(refresh|reload|refresh page|reload page)$"],
                "action": lambda m: self._hotkey(["ctrl", "r"], "Page refreshed"),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "bookmark_page",
                "patterns": [r"^(bookmark page|bookmark this|add bookmark)$"],
                "action": lambda m: self._hotkey(["ctrl", "d"], "Bookmark prompt opened"),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "open_history",
                "patterns": [r"^(open history|browser history|show history)$"],
                "action": lambda m: self._hotkey(["ctrl", "h"], "Opening browser history"),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "open_downloads",
                "patterns": [r"^(open downloads|show downloads)$"],
                "action": lambda m: self._hotkey(["ctrl", "j"], "Opening downloads"),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "incognito_tab",
                "patterns": [r"^(open incognito|new incognito window|private window)$"],
                "action": lambda m: self._hotkey(["ctrl", "shift", "n"], "Opening incognito window"),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "zoom_in",
                "patterns": [r"^(zoom in|make text bigger|increase zoom)$"],
                "action": lambda m: self._hotkey(["ctrl", "+"], "Zoomed in"),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "zoom_out",
                "patterns": [r"^(zoom out|make text smaller|decrease zoom)$"],
                "action": lambda m: self._hotkey(["ctrl", "-"], "Zoomed out"),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "reset_zoom",
                "patterns": [r"^(reset zoom|normal zoom|actual size)$"],
                "action": lambda m: self._hotkey(["ctrl", "0"], "Zoom reset to 100%"),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "scroll_down",
                "patterns": [r"^(scroll down|page down)$"],
                "action": lambda m: self._action_scroll(down=True),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "scroll_up",
                "patterns": [r"^(scroll up|page up)$"],
                "action": lambda m: self._action_scroll(down=False),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "scroll_to_top",
                "patterns": [r"^(scroll to top|go to top|top of page)$"],
                "action": lambda m: self._press_key("home", "Scrolled to top"),
                "type": CommandType.NAVIGATION
            },
            {
                "id": "scroll_to_bottom",
                "patterns": [r"^(scroll to bottom|go to bottom|bottom of page)$"],
                "action": lambda m: self._press_key("end", "Scrolled to bottom"),
                "type": CommandType.NAVIGATION
            },

            # ==========================================
            # 7. Text Editing & Keystrokes (15+)
            # ==========================================
            {
                "id": "type_text",
                "patterns": [r"^type (.+)$", r"^write (.+)$"],
                "action": self._action_type_text,
                "type": CommandType.EDITING
            },
            {
                "id": "select_all",
                "patterns": [r"^(select all|highlight all)$"],
                "action": lambda m: self._hotkey(["ctrl", "a"], "Selected all"),
                "type": CommandType.EDITING
            },
            {
                "id": "copy",
                "patterns": [r"^(copy|copy that|copy this)$"],
                "action": lambda m: self._hotkey(["ctrl", "c"], "Copied to clipboard"),
                "type": CommandType.EDITING
            },
            {
                "id": "paste",
                "patterns": [r"^(paste|paste that|paste this)$"],
                "action": lambda m: self._hotkey(["ctrl", "v"], "Pasted"),
                "type": CommandType.EDITING
            },
            {
                "id": "cut",
                "patterns": [r"^(cut|cut that|cut this)$"],
                "action": lambda m: self._hotkey(["ctrl", "x"], "Cut to clipboard"),
                "type": CommandType.EDITING
            },
            {
                "id": "undo",
                "patterns": [r"^(undo|undo that)$"],
                "action": lambda m: self._hotkey(["ctrl", "z"], "Undone"),
                "type": CommandType.EDITING
            },
            {
                "id": "redo",
                "patterns": [r"^(redo|redo that)$"],
                "action": lambda m: self._hotkey(["ctrl", "y"], "Redone"),
                "type": CommandType.EDITING
            },
            {
                "id": "save_file",
                "patterns": [r"^(save|save file|save this)$"],
                "action": lambda m: self._hotkey(["ctrl", "s"], "Saved"),
                "type": CommandType.EDITING
            },
            {
                "id": "find_in_page",
                "patterns": [r"^(find|find in page|search in file)$"],
                "action": lambda m: self._hotkey(["ctrl", "f"], "Find prompt opened"),
                "type": CommandType.EDITING
            },
            {
                "id": "press_enter",
                "patterns": [r"^press enter$", r"^enter$"],
                "action": lambda m: self._press_key("enter", "Pressed Enter"),
                "type": CommandType.EDITING
            },
            {
                "id": "press_space",
                "patterns": [r"^press space$", r"^spacebar$", r"^space$"],
                "action": lambda m: self._press_key("space", "Pressed Space"),
                "type": CommandType.EDITING
            },
            {
                "id": "press_tab",
                "patterns": [r"^press tab$", r"^tab$"],
                "action": lambda m: self._press_key("tab", "Pressed Tab"),
                "type": CommandType.EDITING
            },
            {
                "id": "press_backspace",
                "patterns": [r"^press backspace$", r"^backspace$", r"^delete character$"],
                "action": lambda m: self._press_key("backspace", "Pressed Backspace"),
                "type": CommandType.EDITING
            },
            {
                "id": "press_escape",
                "patterns": [r"^press escape$", r"^escape$"],
                "action": lambda m: self._press_key("escape", "Pressed Escape"),
                "type": CommandType.EDITING
            },
            {
                "id": "press_delete",
                "patterns": [r"^press delete$", r"^delete$"],
                "action": lambda m: self._press_key("delete", "Pressed Delete"),
                "type": CommandType.EDITING
            },

            # ==========================================
            # 8. Web Search & Information (12+)
            # ==========================================
            {
                "id": "search_google",
                "patterns": [
                    r"^search google for (.+)$",
                    r"^google search (.+)$",
                    r"^search for (.+)$",
                    r"^google (.+)$",
                    r"^search (.+)$",
                    r"^look up (.+)$"
                ],
                "action": self._action_google_search,
                "type": CommandType.WEB
            },
            {
                "id": "search_wikipedia",
                "patterns": [r"^wikipedia (.+)$", r"^wiki (.+)$"],
                "action": self._action_wiki_search,
                "type": CommandType.WEB
            },
            {
                "id": "tell_time",
                "patterns": [r"^(what time is it|what is the time|current time|tell me the time|time please)$"],
                "action": lambda m: self._action_get_time(),
                "type": CommandType.UTILITY
            },
            {
                "id": "tell_date",
                "patterns": [r"^(what is the date|today's date|what date is it|tell me the date|what's the date)$"],
                "action": lambda m: self._action_get_date(),
                "type": CommandType.UTILITY
            },
            {
                "id": "tell_day",
                "patterns": [r"^(what day is today|what day is it|day of the week)$"],
                "action": lambda m: self._action_get_day(),
                "type": CommandType.UTILITY
            },
            {
                "id": "weather",
                "patterns": [r"^weather in (.+)$", r"^what is the weather in (.+)$", r"^weather for (.+)$"],
                "action": self._action_weather_city,
                "type": CommandType.WEB
            },
            {
                "id": "weather_general",
                "patterns": [r"^(what is the weather|weather today|weather forecast|weather)$"],
                "action": lambda m: self._action_weather_general(),
                "type": CommandType.WEB
            },
            {
                "id": "define_word",
                "patterns": [r"^define (.+)$", r"^meaning of (.+)$", r"^what does (.+) mean$"],
                "action": self._action_define_word,
                "type": CommandType.WEB
            },

            # ==========================================
            # 9. Math & Quick Utilities (12+)
            # ==========================================
            {
                "id": "calculate",
                "patterns": [r"^calculate (.+)$", r"^what is (\d+[\s\d\+\-\*\/\%\^\.]+)$"],
                "action": self._action_calculate,
                "type": CommandType.UTILITY
            },
            {
                "id": "tell_joke",
                "patterns": [r"^(tell me a joke|tell a joke|joke|make me laugh)$"],
                "action": lambda m: self._action_tell_joke(),
                "type": CommandType.UTILITY
            },
            {
                "id": "flip_coin",
                "patterns": [r"^(flip a coin|toss a coin|coin flip)$"],
                "action": lambda m: self._action_flip_coin(),
                "type": CommandType.UTILITY
            },
            {
                "id": "roll_dice",
                "patterns": [r"^(roll a dice|roll dice|roll a die)$"],
                "action": lambda m: self._action_roll_dice(),
                "type": CommandType.UTILITY
            },
            {
                "id": "take_note",
                "patterns": [r"^take a note (.+)$", r"^write note (.+)$", r"^note down (.+)$"],
                "action": self._action_take_note,
                "type": CommandType.UTILITY
            },
            {
                "id": "read_notes",
                "patterns": [r"^(read my notes|read notes|show notes|show my notes)$"],
                "action": lambda m: self._action_read_notes(),
                "type": CommandType.UTILITY
            },
            {
                "id": "clear_notes",
                "patterns": [r"^(clear notes|delete notes|empty notes)$"],
                "action": lambda m: self._action_clear_notes(),
                "type": CommandType.UTILITY
            },
            {
                "id": "speed_test",
                "patterns": [r"^(speed test|internet speed|test internet speed)$"],
                "action": lambda m: self._open_url("https://www.speedtest.net", "Running speed test"),
                "type": CommandType.WEB
            },
            {
                "id": "my_ip",
                "patterns": [r"^(what is my ip|my ip address|show my ip)$"],
                "action": lambda m: self._open_url("https://www.whatismyip.com", "Checking your IP address"),
                "type": CommandType.WEB
            },
            {
                "id": "battery_status",
                "patterns": [r"^(battery level|battery status|check battery|how much battery)$"],
                "action": lambda m: self._action_check_battery(),
                "type": CommandType.SYSTEM
            },

            # ==========================================
            # 10. AI Tools & Prompting Suite (10+)
            # ==========================================
            {
                "id": "open_chatgpt",
                "patterns": [r"^(open|launch|go to) chatgpt$", r"^chatgpt$"],
                "action": lambda m: self._open_url("https://chatgpt.com", "Opening ChatGPT"),
                "type": CommandType.AI
            },
            {
                "id": "open_claude",
                "patterns": [r"^(open|launch|go to) claude$", r"^claude ai$"],
                "action": lambda m: self._open_url("https://claude.ai", "Opening Claude AI"),
                "type": CommandType.AI
            },
            {
                "id": "open_copilot",
                "patterns": [r"^(open|launch|go to) copilot$", r"^microsoft copilot$"],
                "action": lambda m: self._open_url("https://copilot.microsoft.com", "Opening Microsoft Copilot"),
                "type": CommandType.AI
            },
            {
                "id": "open_perplexity",
                "patterns": [r"^(open|launch|go to) perplexity$", r"^perplexity ai$"],
                "action": lambda m: self._open_url("https://www.perplexity.ai", "Opening Perplexity AI"),
                "type": CommandType.AI
            },
            {
                "id": "open_gemini",
                "patterns": [r"^(open|launch|go to) (gemini|google gemini)$"],
                "action": lambda m: self._open_url("https://gemini.google.com", "Opening Google Gemini"),
                "type": CommandType.AI
            },
            {
                "id": "ask_chatgpt",
                "patterns": [r"^(ask|prompt) chatgpt (.+)$"],
                "action": lambda m: self._action_ask_ai("chatgpt", m),
                "type": CommandType.AI
            },
            {
                "id": "ask_perplexity",
                "patterns": [r"^(ask|search) perplexity (.+)$"],
                "action": lambda m: self._action_ask_ai("perplexity", m),
                "type": CommandType.AI
            },
            {
                "id": "ask_copilot",
                "patterns": [r"^(ask|prompt) copilot (.+)$"],
                "action": lambda m: self._action_ask_ai("copilot", m),
                "type": CommandType.AI
            },
            {
                "id": "ask_claude",
                "patterns": [r"^(ask|prompt) claude (.+)$"],
                "action": lambda m: self._action_ask_ai("claude", m),
                "type": CommandType.AI
            },
            {
                "id": "ai_summarize",
                "patterns": [r"^(summarize this with ai|ai summarize|summarize this text|summarize selection)$"],
                "action": lambda m: self._action_ai_summarize(),
                "type": CommandType.AI
            },
            {
                "id": "ai_fix_code",
                "patterns": [r"^(fix (this )?code with ai|explain (this )?code with ai|debug (this )?code with ai)$"],
                "action": lambda m: self._action_ai_code(),
                "type": CommandType.AI
            },

            # ==========================================
            # 11. Smart File Locator (Windows Explorer Integration)
            # ==========================================
            {
                "id": "find_file",
                "patterns": [
                    r"^(?:where is|where did i save|find file|locate file|search file|locate) (.+?)(?: in (.+))?$",
                    r"^find (.+?) in (.+)$"
                ],
                "action": self._action_find_file,
                "type": CommandType.FILE
            },

            # ==========================================
            # 12. Conversational & Friendly Speeches (JARVIS Personality)
            # ==========================================
            {
                "id": "are_you_there",
                "patterns": [r"^(are you there|you there jarvis|you there|jarvis are you there)$"],
                "action": lambda m: random.choice([
                    "For you, sir, always.",
                    "Online and fully operational! Ready for your command.",
                    "Right here beside you. How can I assist?",
                    "Standing by and listening!"
                ]),
                "type": CommandType.SYSTEM
            },
            {
                "id": "identity",
                "patterns": [r"^(who are you|what is your name|what's your name)$"],
                "action": lambda m: "I am JARVIS, your intelligent personal AI voice companion.",
                "type": CommandType.SYSTEM
            },
            {
                "id": "good_morning",
                "patterns": [r"^good morning( jarvis)?$"],
                "action": lambda m: random.choice([
                    "Good morning! Wishing you an energized and productive day ahead. What's on our agenda?",
                    "Rise and shine! JARVIS is online and ready. How can I help you kick off the day?",
                    "Good morning! All systems are optimal and ready for your commands."
                ]),
                "type": CommandType.SYSTEM
            },
            {
                "id": "good_afternoon",
                "patterns": [r"^good afternoon( jarvis)?$"],
                "action": lambda m: random.choice([
                    "Good afternoon! Hope everything is progressing smoothly. What would you like to do next?",
                    "Good afternoon! Ready when you are."
                ]),
                "type": CommandType.SYSTEM
            },
            {
                "id": "good_evening",
                "patterns": [r"^good evening( jarvis)?$"],
                "action": lambda m: random.choice([
                    "Good evening! Time to wind down or wrap up some tasks. How can I assist you?",
                    "Good evening! I hope you've had a satisfying day."
                ]),
                "type": CommandType.SYSTEM
            },
            {
                "id": "good_night",
                "patterns": [r"^good night( jarvis)?$"],
                "action": lambda m: random.choice([
                    "Good night! Rest well and recharge. I'll be here when you return.",
                    "Good night! Standing by in low-power idle."
                ]),
                "type": CommandType.SYSTEM
            },
            {
                "id": "how_are_you",
                "patterns": [r"^(how are you|how are you doing|how is it going|how do you feel|how was your day)$"],
                "action": lambda m: random.choice([
                    "I am functioning at 100% efficiency and feeling fantastic! How about you?",
                    "All systems are green and running smoothly! What's on your mind today?",
                    "Never better! Ready to tackle whatever you have in mind."
                ]),
                "type": CommandType.SYSTEM
            },
            {
                "id": "compliment_me",
                "patterns": [r"^(compliment me|say something nice|praise me)$"],
                "action": lambda m: random.choice([
                    "You have great vision, incredible determination, and you're doing amazing work today!",
                    "You're sharp, resourceful, and capable of solving any challenge. Keep going!",
                    "It's genuinely a pleasure working with you. You make things happen!"
                ]),
                "type": CommandType.SYSTEM
            },
            {
                "id": "bored",
                "patterns": [r"^(i am bored|i'm bored|feeling bored)$"],
                "action": lambda m: random.choice([
                    "Boredom is just waiting for a spark! Would you like me to play some music on YouTube, tell an interesting fact, or test your internet speed?",
                    "How about exploring something new? I can find a great video on YouTube, tell you a joke, or we can look up a fascinating topic!"
                ]),
                "type": CommandType.SYSTEM
            },
            {
                "id": "tell_quote",
                "patterns": [r"^(tell me a quote|inspire me|motivate me|quote of the day)$"],
                "action": lambda m: random.choice([
                    "'The secret of getting ahead is getting started.' — Mark Twain",
                    "'It always seems impossible until it's done.' — Nelson Mandela",
                    "'The best way to predict the future is to invent it.' — Alan Kay",
                    "'Success is not final, failure is not fatal: it is the courage to continue that counts.' — Winston Churchill"
                ]),
                "type": CommandType.SYSTEM
            },
            {
                "id": "tell_fact",
                "patterns": [r"^(tell me a fact|interesting fact|fun fact|random fact)$"],
                "action": lambda m: random.choice([
                    "Did you know? Honey never spoils — archaeologists have found edible honey in ancient Egyptian tombs that is over 3,000 years old!",
                    "Did you know? The first computer programmer in history was Ada Lovelace in the 1840s.",
                    "Did you know? Octopuses have three hearts and their blood is blue!",
                    "Did you know? The world's first webcam was created at Cambridge University to check the status of a coffee pot!"
                ]),
                "type": CommandType.SYSTEM
            },
            {
                "id": "cheer_me_up",
                "patterns": [r"^(cheer me up|make me happy|i feel sad)$"],
                "action": lambda m: random.choice([
                    "Take a deep breath. You've handled 100% of difficult days so far, and today is another victory waiting for you!",
                    "No matter how tough things feel, you have the resilience to overcome it. I'm right here with you!",
                    "Remember: Even the darkest night will end and the sun will rise. You've got this!"
                ]),
                "type": CommandType.SYSTEM
            },
            {
                "id": "thanks",
                "patterns": [r"^(thank you|thanks|thanks a lot|thank you so much)$"],
                "action": lambda m: random.choice([
                    "You are very welcome! Always happy to assist.",
                    "Anytime! Let me know if there's anything else you need.",
                    "My pleasure, sir!"
                ]),
                "type": CommandType.SYSTEM
            },
            {
                "id": "repeat_last",
                "patterns": [r"^(repeat that|say that again|repeat|what did you say)$"],
                "action": lambda m: f"I said: {self.last_response}",
                "type": CommandType.SYSTEM
            },
            {
                "id": "help_commands",
                "patterns": [r"^(help|what can you do|show commands|list commands|available commands)$"],
                "action": lambda m: "I can open applications, control YouTube playback and downloads, prompt ChatGPT and Copilot, locate files in File Explorer, manage volume, and much more. Check VOICE_COMMANDS.md for details.",
                "type": CommandType.SYSTEM
            },
            {
                "id": "exit",
                "patterns": [r"^(exit|quit|stop assistant|goodbye|bye|close assistant)$"],
                "action": lambda m: "Goodbye! Have a great day.",
                "type": CommandType.SYSTEM
            }
        ]

    # --- Action Implementations ---

    def _open_url(self, url: str, msg: str) -> str:
        webbrowser.open(url)
        return msg

    def _press_key(self, key: str, msg: str) -> str:
        pyautogui.press(key)
        return msg

    def _hotkey(self, keys: List[str], msg: str) -> str:
        pyautogui.hotkey(*keys)
        return msg

    def _launch_app(self, command: str, msg: str) -> str:
        try:
            subprocess.Popen(command, shell=True)
            return msg
        except Exception as e:
            logger.error(f"Failed to launch app: {e}")
            return f"Sorry, could not open application."

    def _change_volume(self, up: bool = True, steps: int = 5, msg: Optional[str] = None) -> str:
        key = "volumeup" if up else "volumedown"
        for _ in range(steps):
            pyautogui.press(key)
            time.sleep(0.02)
        if msg:
            return msg
        return "Volume increased" if up else "Volume decreased"

    def _action_play_youtube(self, match) -> str:
        # Pattern may have 1 or 2 groups depending on which regex matched.
        # Group 1 is always the search query for all our patterns.
        try:
            query = match.group(1).strip()
            # If query looks like the full sentence (fuzzy fallback), clean it
            for prefix in ["play ", "search youtube for ", "youtube search "]:
                if query.lower().startswith(prefix):
                    query = query[len(prefix):].strip()
            # Remove trailing " on youtube" or " youtube" if captured
            for suffix in [" on youtube", " in youtube", " youtube"]:
                if query.lower().endswith(suffix):
                    query = query[: -len(suffix)].strip()
        except (IndexError, AttributeError):
            query = "music"
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        webbrowser.open(url)
        return f"Searching YouTube for {query}"

    def _action_download_youtube(self, match, audio_only: bool = False) -> str:
        """Download a YouTube video or audio track using yt_dlp Python API."""
        raw_target = None
        try:
            groups = match.groups() if match else ()
            # Pattern 1: ^download (this|current|the)? ?(video|song|...)( (.+))?$
            #   group(1)=keyword, group(2)=type, group(3)=suffix-with-name, group(4)=name
            # Pattern 2: ^download (.+) (from|on) youtube$
            #   group(1)=name, group(2)='from'/'on'
            # Pattern 3 (audio): ^download audio of (.+)$
            #   group(1)=name
            for i in range(len(groups) - 1, -1, -1):
                g = groups[i]
                if g and g.strip() and g.strip().lower() not in (
                    "this", "current", "the", "from", "on",
                    "video", "song", "youtube video", "mp3", "audio"
                ):
                    raw_target = g.strip()
                    break
        except Exception:
            pass

        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(downloads_dir, exist_ok=True)

        def _do_download():
            target = raw_target

            # If no explicit target, try clipboard for a YouTube URL
            if not target:
                try:
                    clip = pyperclip.paste().strip()
                    if "youtube.com" in clip or "youtu.be" in clip:
                        target = clip
                except Exception:
                    pass

            # Last resort: search for a trending song
            if not target:
                target = "ytsearch1:trending song"

            # Prefix non-URL targets with ytsearch
            if not target.startswith("http") and not target.startswith("ytsearch"):
                target = f"ytsearch1:{target}"

            try:
                import yt_dlp
                ydl_opts = {
                    "outtmpl": os.path.join(downloads_dir, "%(title)s.%(ext)s"),
                    "noplaylist": True,
                    "quiet": True,
                    "no_warnings": True,
                }
                if audio_only:
                    ydl_opts.update({
                        "format": "bestaudio/best",
                        "postprocessors": [{
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }],
                    })
                else:
                    ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([target])
                logger.info(f"YouTube download complete: {target}")
            except Exception as e:
                logger.error(f"Download error: {e}")

        threading.Thread(target=_do_download, daemon=True).start()
        filetype = "audio track" if audio_only else "video"
        return f"Starting {filetype} download to your Downloads folder in the background."

    def _action_ask_ai(self, provider: str, match) -> str:
        try:
            query = match.group(2).strip()
        except Exception:
            try:
                query = match.group(1).strip()
            except Exception:
                query = "Hello"
        encoded = urllib.parse.quote_plus(query)
        if provider == "chatgpt":
            url = f"https://chatgpt.com/?q={encoded}"
            name = "ChatGPT"
        elif provider == "perplexity":
            url = f"https://www.perplexity.ai/search?q={encoded}"
            name = "Perplexity AI"
        elif provider == "copilot":
            url = f"https://copilot.microsoft.com/?q={encoded}"
            name = "Copilot"
        elif provider == "claude":
            url = "https://claude.ai/new"
            name = "Claude"
            pyperclip.copy(query)
        else:
            url = f"https://www.google.com/search?q={encoded}"
            name = "AI"

        webbrowser.open(url)
        return f"Asking {name}: {query}"

    def _action_ai_summarize(self) -> str:
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.15)
        text = pyperclip.paste().strip()
        if not text:
            return "Please select or highlight some text first so I can summarize it."
        prompt = f"Please summarize the following text clearly:\n\n{text[:1200]}"
        encoded = urllib.parse.quote_plus(prompt)
        webbrowser.open(f"https://www.perplexity.ai/search?q={encoded}")
        return "Sending your selected text to Perplexity AI for summarization."

    def _action_ai_code(self) -> str:
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.15)
        code = pyperclip.paste().strip()
        if not code:
            return "Please select the code you want me to explain or debug."
        prompt = f"Please explain this code and fix any bugs or optimizations:\n\n{code[:1200]}"
        encoded = urllib.parse.quote_plus(prompt)
        webbrowser.open(f"https://www.perplexity.ai/search?q={encoded}")
        return "Sending your code selection to AI for analysis and fixes."

    def _action_find_file(self, match) -> str:
        try:
            filename = match.group(1).strip()
            for prefix in ["the file ", "file ", "a file "]:
                if filename.lower().startswith(prefix):
                    filename = filename[len(prefix):].strip()
            location = None
            if len(match.groups()) >= 2 and match.group(2):
                location = match.group(2).strip()
        except Exception:
            return "Please tell me the name of the file you are looking for."

        if not filename:
            return "Please specify a file name to search for."

        start_time = time.time()
        timeout_sec = 5.0
        query_lower = filename.lower()

        user_home = os.path.expanduser("~")
        roots = []
        if location:
            loc_lower = location.lower()
            if "c drive" in loc_lower or loc_lower == "c":
                roots.append("C:\\")
            elif "d drive" in loc_lower or loc_lower == "d":
                roots.append("D:\\")
            elif "e drive" in loc_lower or loc_lower == "e":
                roots.append("E:\\")
            elif "desktop" in loc_lower:
                roots.append(os.path.join(user_home, "Desktop"))
            elif "document" in loc_lower:
                roots.append(os.path.join(user_home, "Documents"))
            elif "download" in loc_lower:
                roots.append(os.path.join(user_home, "Downloads"))
            elif "project" in loc_lower:
                roots.extend([
                    "E:\\Btech Essentials",
                    os.path.join(user_home, "Projects"),
                    "C:\\Projects"
                ])
            elif os.path.exists(location):
                roots.append(location)

        if not roots:
            roots = [
                os.path.join(user_home, "Desktop"),
                os.path.join(user_home, "Documents"),
                os.path.join(user_home, "Downloads"),
                "E:\\Btech Essentials\\JARVIS",
                "C:\\Users\\Admin"
            ]

        skip_dirs = {
            "node_modules", ".git", "__pycache__", "$recycle.bin",
            "system volume information", "appdata", "windows", "winsxs"
        }
        found_path = None

        for root_dir in roots:
            if not os.path.exists(root_dir):
                continue
            for current_root, dirs, files in os.walk(root_dir):
                if time.time() - start_time > timeout_sec:
                    break
                dirs[:] = [d for d in dirs if d.lower() not in skip_dirs]
                for f in files:
                    if query_lower == f.lower() or query_lower in f.lower():
                        found_path = os.path.join(current_root, f)
                        break
                if found_path:
                    break
            if found_path:
                break

        if found_path:
            try:
                subprocess.Popen(f'explorer /select,"{os.path.abspath(found_path)}"')
            except Exception as e:
                logger.error(f"Failed to open explorer: {e}")
            folder_name = os.path.basename(os.path.dirname(found_path))
            return f"Found {os.path.basename(found_path)} in {folder_name}. Highlighting it in File Explorer."
        else:
            return f"I searched the selected locations for 5 seconds but could not locate {filename}."

    def _action_google_search(self, match) -> str:
        try:
            query = match.group(1).strip()
            for prefix in ["google for ", "google ", "for "]:
                if query.lower().startswith(prefix):
                    query = query[len(prefix):].strip()
        except (IndexError, AttributeError):
            query = "Google"
        encoded = urllib.parse.quote_plus(query)
        webbrowser.open(f"https://www.google.com/search?q={encoded}")
        return f"Searching Google for {query}"

    def _action_wiki_search(self, match) -> str:
        query = match.group(1).strip()
        encoded = urllib.parse.quote_plus(query)
        webbrowser.open(f"https://en.wikipedia.org/wiki/Special:Search?search={encoded}")
        return f"Searching Wikipedia for {query}"

    def _action_weather_city(self, match) -> str:
        city = match.group(1).strip()
        encoded = urllib.parse.quote_plus(f"weather {city}")
        webbrowser.open(f"https://www.google.com/search?q={encoded}")
        return f"Checking weather for {city}"

    def _action_weather_general(self) -> str:
        webbrowser.open("https://www.google.com/search?q=weather")
        return "Showing the current weather forecast"

    def _action_define_word(self, match) -> str:
        word = match.group(1).strip()
        encoded = urllib.parse.quote_plus(f"define {word}")
        webbrowser.open(f"https://www.google.com/search?q={encoded}")
        return f"Looking up the definition of {word}"

    def _action_type_text(self, match) -> str:
        text_to_type = match.group(1).strip()
        try:
            pyperclip.copy(text_to_type)
            pyautogui.hotkey('ctrl', 'v')
            return f"Typed: {text_to_type}"
        except Exception:
            pyautogui.write(text_to_type)
            return f"Typed: {text_to_type}"

    def _action_get_time(self) -> str:
        now = datetime.datetime.now()
        return f"The current time is {now.strftime('%I:%M %p')}"

    def _action_get_date(self) -> str:
        now = datetime.datetime.now()
        return f"Today is {now.strftime('%A, %B %d, %Y')}"

    def _action_get_day(self) -> str:
        now = datetime.datetime.now()
        return f"Today is {now.strftime('%A')}"

    def _action_scroll(self, down: bool = True) -> str:
        amount = -600 if down else 600
        pyautogui.scroll(amount)
        return "Scrolled down" if down else "Scrolled up"

    def _action_lock_pc(self) -> str:
        try:
            os.system("rundll32.exe user32.dll,LockWorkStation")
            return "Locking the workstation"
        except Exception as e:
            logger.error(f"Error locking PC: {e}")
            return "Could not lock workstation"

    def _action_take_screenshot(self) -> str:
        try:
            os.makedirs("screenshots", exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join("screenshots", f"screenshot_{timestamp}.png")
            screenshot = pyautogui.screenshot()
            screenshot.save(filename)
            return f"Screenshot saved to {filename}"
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return "Failed to take screenshot"

    def _action_empty_recycle_bin(self) -> str:
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            return "Recycle Bin emptied"
        except Exception as e:
            logger.error(f"Error emptying recycle bin: {e}")
            return "Could not empty recycle bin"

    def _action_check_battery(self) -> str:
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                plugged = "plugged in" if battery.power_plugged else "on battery"
                return f"Battery is at {battery.percent:.0f} percent and {plugged}"
        except Exception:
            pass
        return "Battery status information is unavailable."

    def _action_calculate(self, match) -> str:
        expr = match.group(1).strip()
        # Clean expression
        sanitized = re.sub(r'[^0-9\+\-\*\/\%\(\)\.\^ ]', '', expr)
        sanitized = sanitized.replace('^', '**')
        try:
            # Safe evaluation for basic arithmetic
            result = eval(sanitized, {"__builtins__": None}, {})
            return f"{expr} is {result}"
        except Exception:
            return f"Sorry, could not calculate {expr}"

    def _action_tell_joke(self) -> str:
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs!",
            "There are 10 types of people in the world: those who understand binary, and those who don't.",
            "Why did the computer go to the doctor? Because it had a virus!",
            "What is a programmer's favorite hangout spot? The Foo Bar.",
            "A SQL statement walks into a bar, approaches two tables, and asks: May I join you?",
            "Why was the JavaScript developer sad? Because they didn't Node how to Express themselves!",
            "What did one computer say to the other? Between 0 and 1, you're my favorite."
        ]
        return random.choice(jokes)

    def _action_flip_coin(self) -> str:
        result = random.choice(["Heads", "Tails"])
        return f"It's {result}!"

    def _action_roll_dice(self) -> str:
        result = random.randint(1, 6)
        return f"You rolled a {result}!"

    def _action_take_note(self, match) -> str:
        note_content = match.group(1).strip()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.notes_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {note_content}\n")
            return f"Saved note: {note_content}"
        except Exception as e:
            logger.error(f"Note save error: {e}")
            return "Could not save note"

    def _action_read_notes(self) -> str:
        if not os.path.exists(self.notes_file):
            return "You don't have any notes saved yet."
        try:
            with open(self.notes_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if not lines:
                return "Your notes file is empty."
            recent = [line.strip() for line in lines[-3:] if line.strip()]
            return "Your most recent notes are: " + " ; ".join(recent)
        except Exception as e:
            logger.error(f"Note read error: {e}")
            return "Could not read notes."

    def _action_clear_notes(self) -> str:
        try:
            with open(self.notes_file, "w", encoding="utf-8") as f:
                f.write("")
            return "Your notes have been cleared."
        except Exception as e:
            logger.error(f"Error clearing notes: {e}")
            return "Could not clear notes."

    def process(self, text: str) -> Dict[str, Any]:
        """Match and execute a command from input text."""
        cleaned_text = text.lower().strip()
        
        # 1. Check Regex Patterns
        for cmd in self.commands:
            for pattern in cmd["patterns"]:
                match = re.search(pattern, cleaned_text, re.IGNORECASE)
                if match:
                    try:
                        response = cmd["action"](match)
                        self.last_response = response
                        return {
                            "id": cmd["id"],
                            "type": cmd["type"],
                            "response": response,
                            "confidence": 1.0
                        }
                    except Exception as e:
                        logger.error(f"Error executing command {cmd['id']}: {e}")
                        return {
                            "id": cmd["id"],
                            "type": cmd["type"],
                            "response": "An error occurred while executing that command.",
                            "confidence": 1.0
                        }

        # 2. Check Fuzzy Matching for Common Simple Commands
        best_cmd = None
        best_score = 0
        for cmd in self.commands:
            for pattern in cmd["patterns"]:
                # Strip regex symbols for comparison
                plain = re.sub(r'[\^\$\(\)\|\?\+\*\\]', '', pattern).strip()
                score = fuzz.ratio(plain.lower(), cleaned_text)
                if score > 78 and score > best_score:
                    best_score = score
                    best_cmd = cmd

        if best_cmd:
            try:
                # Create dummy match
                match = re.search(r'(.*)', cleaned_text)
                response = best_cmd["action"](match)
                self.last_response = response
                return {
                    "id": best_cmd["id"],
                    "type": best_cmd["type"],
                    "response": response,
                    "confidence": best_score / 100.0
                }
            except Exception as e:
                logger.error(f"Fuzzy execution error: {e}")

        # 3. Intelligent AI Agent Fallback (DeepSeek Brain with tool calling)
        if hasattr(self, 'ai_agent') and self.ai_agent:
            try:
                response = self.ai_agent.process(text)
                self.last_response = response
                return {
                    "id": "ai_agent_response",
                    "type": CommandType.AI,
                    "response": response,
                    "confidence": 0.95
                }
            except Exception as e:
                logger.error(f"AI Agent processing error: {e}")

        # 4. Final Fallback: Google Search
        response = f"I didn't recognize that command directly, searching Google for {text}"
        webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote_plus(text)}")
        self.last_response = response
        return {
            "id": "search_fallback",
            "type": CommandType.WEB,
            "response": response,
            "confidence": 0.5
        }


class VoiceInterface:
    """Handles microphone capture, TTS speech output, and assistant coordination."""

    def __init__(self, config_file: str = "voice_config.json", status_callback: Optional[Callable[[str], None]] = None):
        self.config_file = config_file
        self.status_callback = status_callback
        self.config = self._load_config()
        self.wake_word = self.config.get("wake_word", "JARVIS").lower()
        self.require_wake_word = self.config.get("require_wake_word", False)
        
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = self.config.get("energy_threshold", 300)
        self.recognizer.pause_threshold = self.config.get("pause_threshold", 0.8)
        
        self.engine = None
        self._init_tts()
        
        # Initialize AI Agent brain
        self.ai_agent = None
        if self.config.get("enable_ai_agent", True):
            try:
                self.ai_agent = AIAgent(
                    model=self.config.get("hf_model", "Qwen/Qwen2.5-72B-Instruct"),
                    temperature=self.config.get("ai_temperature", 0.3),
                    status_callback=self.status_callback,
                    provider=self.config.get("ai_provider", "huggingface")
                )
            except Exception as e:
                logger.error(f"Could not initialize AI Agent: {e}")

        self.processor = VoiceCommandProcessor()
        self.processor.ai_agent = self.ai_agent
        self.microphone = None
        self.is_listening = False
        self._stop_event = threading.Event()
        self._listen_thread = None
        self.command_callback = None
        
        try:
            self.microphone = sr.Microphone()
        except Exception as e:
            logger.warning(f"Could not initialize microphone: {e}")

    def _load_config(self) -> Dict[str, Any]:
        default = {
            "language": "en-US",
            "voice_rate": 160,
            "voice_volume": 1.0,
            "wake_word": "JARVIS",
            "require_wake_word": False,
            "energy_threshold": 300,
            "pause_threshold": 0.8
        }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return {**default, **json.load(f)}
            except Exception as e:
                logger.error(f"Error loading {self.config_file}: {e}")
        return default

    def _save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def _init_tts(self):
        self._tts_lock = threading.Lock()
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", self.config.get("voice_rate", 160))
            self.engine.setProperty("volume", self.config.get("voice_volume", 1.0))
        except Exception as e:
            logger.error(f"Failed to initialize TTS engine: {e}")
            self.engine = None

    def _speak_rumik(self, text: str) -> bool:
        """Synthesize and play speech using Rumik AI Silk TTS."""
        api_key = os.getenv("RUMIK_API_KEY", "rk_live_Mb5_0-QAzl5JjVR5JtB7rqzYyLRqMTAyFzj9LevmwGA")
        if not api_key:
            return False

        try:
            import httpx
            import winsound

            url = os.getenv("RUMIK_API_URL", "https://silk-api.rumik.ai/v1/tts")
            model = self.config.get("rumik_model", "muga")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "text": text,
                "model": model
            }

            response = httpx.post(url, headers=headers, json=payload, timeout=12.0)
            if response.status_code == 200 and len(response.content) > 0:
                temp_file = os.path.join(
                    tempfile.gettempdir(),
                    f"JARVIS_rumik_{os.getpid()}_{int(time.time() * 1000)}.wav"
                )
                with open(temp_file, "wb") as f:
                    f.write(response.content)

                # Play WAV audio
                winsound.PlaySound(temp_file, winsound.SND_FILENAME)
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
                return True
            else:
                logger.warning(
                    f"Rumik AI TTS error (Status {response.status_code}: {response.text[:150]}). "
                    "Falling back to default neural/local voice."
                )
                return False
        except Exception as e:
            logger.warning(f"Rumik TTS synthesis failed ({e}). Falling back to default voice.")
            return False

    def _speak_neural(self, text: str) -> bool:
        """Synthesize and play speech with human-sounding Neural voice."""
        try:
            import edge_tts
            voice = self.config.get("neural_voice", "en-IN-NeerjaNeural")
            temp_file = os.path.join(
                tempfile.gettempdir(),
                f"JARVIS_speech_{os.getpid()}_{int(time.time() * 1000)}.mp3"
            )

            async def _synth():
                comm = edge_tts.Communicate(text, voice)
                await comm.save(temp_file)

            asyncio.run(_synth())

            if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
                return False

            alias = f"JARVIS_audio_{int(time.time() * 1000)}"
            ctypes.windll.winmm.mciSendStringW(f'open "{temp_file}" type mpegvideo alias {alias}', None, 0, None)
            ctypes.windll.winmm.mciSendStringW(f'play {alias} wait', None, 0, None)
            ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, None)

            try:
                os.remove(temp_file)
            except Exception:
                pass
            return True
        except Exception as e:
            logger.warning(f"Neural TTS failed, falling back to local TTS: {e}")
            return False

    def speak(self, text: str, wait: bool = False):
        """Speak output text using Rumik AI Silk TTS (primary) with fallback to Neural and pyttsx3."""
        print(f"\n[JARVIS]: {text}")

        def _speak_thread():
            with self._tts_lock:
                # 1. Primary: Rumik AI Silk TTS
                tts_engine = self.config.get("tts_engine", "rumik")
                if tts_engine == "rumik":
                    if self._speak_rumik(text):
                        return

                # 2. Secondary Fallback: Microsoft Natural Neural Voice
                if tts_engine in ["rumik", "neural"]:
                    if self._speak_neural(text):
                        return

                # 3. Tertiary Fallback: Offline pyttsx3
                if self.engine:
                    try:
                        self.engine.say(text)
                        self.engine.runAndWait()
                    except Exception as e:
                        logger.error(f"TTS Speech error: {e}")

        if wait:
            _speak_thread()
        else:
            t = threading.Thread(target=_speak_thread, daemon=True)
            t.start()

    def set_rate(self, delta: int):
        current = self.config.get("voice_rate", 160)
        new_rate = max(100, min(300, current + delta))
        self.config["voice_rate"] = new_rate
        if self.engine:
            self.engine.setProperty("rate", new_rate)
        self._save_config()

    def set_volume(self, delta: float):
        current = self.config.get("voice_volume", 1.0)
        new_vol = max(0.1, min(1.0, current + delta))
        self.config["voice_volume"] = new_vol
        if self.engine:
            self.engine.setProperty("volume", new_vol)
        self._save_config()

    def execute_text_command(self, raw_text: str) -> str:
        """Process and execute text directly."""
        clean_text = raw_text.strip()
        if not clean_text:
            return ""

        # Check for assistant-specific voice settings commands
        lowered = clean_text.lower()
        if lowered in ["speak faster", "talk faster", "faster"]:
            self.set_rate(25)
            response = "Speech rate increased"
            self.speak(response)
            return response
        elif lowered in ["speak slower", "talk slower", "slower"]:
            self.set_rate(-25)
            response = "Speech rate decreased"
            self.speak(response)
            return response
        elif lowered in ["speak louder", "talk louder", "louder"]:
            self.set_volume(0.2)
            response = "Volume increased"
            self.speak(response)
            return response
        elif lowered in ["speak softer", "talk softer", "softer"]:
            self.set_volume(-0.2)
            response = "Volume decreased"
            self.speak(response)
            return response
        elif lowered in ["switch to female voice", "use female voice", "female voice"]:
            self.config["tts_engine"] = "neural"
            self.config["neural_voice"] = "en-IN-NeerjaNeural"
            self._save_config()
            response = "Switched to natural female voice."
            self.speak(response)
            return response
        elif lowered in ["switch to male voice", "use male voice", "male voice"]:
            self.config["tts_engine"] = "neural"
            self.config["neural_voice"] = "en-IN-PrabhatNeural"
            self._save_config()
            response = "Switched to natural male voice."
            self.speak(response)
            return response
        elif lowered in ["switch to american voice", "use american voice", "american voice"]:
            self.config["tts_engine"] = "neural"
            self.config["neural_voice"] = "en-US-AvaNeural"
            self._save_config()
            response = "Switched to American natural voice."
            self.speak(response)
            return response
        elif lowered in ["use robotic voice", "switch to robotic voice", "offline voice"]:
            self.config["tts_engine"] = "pyttsx3"
            self._save_config()
            response = "Switched to offline local voice."
            self.speak(response)
            return response
        elif lowered in ["use human voice", "switch to human voice", "use neural voice"]:
            self.config["tts_engine"] = "neural"
            self._save_config()
            response = "Switched to human neural voice."
            self.speak(response)
            return response

        result = self.processor.process(clean_text)
        response = result.get("response", "")
        if response:
            self.speak(response)
        return response

    def start_listening(self, callback: Optional[Callable[[VoiceCommand], None]] = None):
        """Begin listening continuously in background thread."""
        if self.is_listening:
            return

        if not self.microphone:
            logger.error("No microphone available to start listening.")
            return

        self.command_callback = callback
        self.is_listening = True
        self._stop_event.clear()

        self._listen_thread = threading.Thread(
            target=self._listen_worker,
            daemon=True,
            name="JARVISListenWorker"
        )
        self._listen_thread.start()
        logger.info("Voice interface started listening")

    def _listen_worker(self):
        with self.microphone as source:
            try:
                print("[Microphone]: Calibrating for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1.2)
                print("[Microphone]: Calibration complete. Ready for voice commands!")
            except Exception as e:
                logger.error(f"Microphone adjustment error: {e}")

            while self.is_listening and not self._stop_event.is_set():
                try:
                    audio = self.recognizer.listen(source, timeout=2.0, phrase_time_limit=6.0)
                    try:
                        text = self.recognizer.recognize_google(audio).strip()
                        if not text:
                            continue

                        print(f"\n[You]: {text}")
                        lowered = text.lower()

                        # Check wake word if required
                        command_text = text
                        wake = self.wake_word
                        if self.require_wake_word:
                            if lowered.startswith(wake):
                                command_text = text[len(wake):].strip()
                            else:
                                continue
                        else:
                            # Strip wake word if present for cleaner matching
                            if lowered.startswith(wake):
                                command_text = text[len(wake):].strip()

                        if not command_text:
                            self.speak("Yes, I am listening.")
                            continue

                        response = self.execute_text_command(command_text)

                        if self.command_callback:
                            cmd_obj = VoiceCommand(text=command_text, response=response)
                            self.command_callback(cmd_obj)

                    except sr.UnknownValueError:
                        pass
                    except sr.RequestError as e:
                        logger.error(f"Speech recognition service error: {e}")
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Audio capture error: {e}")
                    time.sleep(0.2)

    def stop_listening(self):
        """Stop listening thread gracefully."""
        self.is_listening = False   # signal the while-loop to exit
        self._stop_event.set()      # also wake any blocking waits
        if self._listen_thread and self._listen_thread.is_alive():
            # Wait long enough for the listen() call to time out (timeout=2.0 + buffer)
            self._listen_thread.join(timeout=4.0)
            if self._listen_thread.is_alive():
                logger.warning("Listen thread did not exit cleanly within timeout.")
        self._listen_thread = None
        logger.info("Voice interface stopped")
