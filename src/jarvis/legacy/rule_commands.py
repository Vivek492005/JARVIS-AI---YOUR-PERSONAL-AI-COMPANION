# ruff: noqa: E501  (generated file — long string constants are data)
"""Reflex rule data — AST-extracted from the legacy voice command table.

DO NOT EDIT BY HAND. Regenerate with scripts/extract_reflex_rules.py
after changing src/jarvis/voice/interface.py.

Each rule: patterns -> ToolSpec call (policy-gated by the router)
or a computed/reply-only response. Template syntax in args/reply:
  {groupN}            regex group N (1-based)
  {groupN|urlencode}  URL-encoded group
  {groupN|default:X}  X when the group is empty/missing
"""

RULES = [
    {
        "id": "open_youtube",
        "patterns": [
            "^(open|go to|launch) youtube$",
            "^youtube$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.youtube.com"},
        "reply": "Opening YouTube",
        "compute": None,
    },
    {
        "id": "open_linkedin",
        "patterns": [
            "^(open|go to|launch) linkedin$",
            "^linkedin$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.linkedin.com"},
        "reply": "Opening LinkedIn",
        "compute": None,
    },
    {
        "id": "open_gmail",
        "patterns": [
            "^(open|go to|launch|check) (gmail|email|mail)$",
            "^gmail$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://mail.google.com"},
        "reply": "Opening Gmail",
        "compute": None,
    },
    {
        "id": "open_github",
        "patterns": [
            "^(open|go to|launch) github$",
            "^github$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://github.com"},
        "reply": "Opening GitHub",
        "compute": None,
    },
    {
        "id": "open_google",
        "patterns": [
            "^(open|go to|launch) google$",
            "^google$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.google.com"},
        "reply": "Opening Google",
        "compute": None,
    },
    {
        "id": "open_whatsapp",
        "patterns": [
            "^(open|go to|launch) (whatsapp|whatsapp web)$",
            "^whatsapp$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://web.whatsapp.com"},
        "reply": "Opening WhatsApp Web",
        "compute": None,
    },
    {
        "id": "open_chatgpt",
        "patterns": [
            "^(open|go to|launch) (chat gpt|chatgpt|openai)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://chat.openai.com"},
        "reply": "Opening ChatGPT",
        "compute": None,
    },
    {
        "id": "open_twitter",
        "patterns": [
            "^(open|go to|launch) (twitter|x)$",
            "^twitter$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://twitter.com"},
        "reply": "Opening Twitter",
        "compute": None,
    },
    {
        "id": "open_instagram",
        "patterns": [
            "^(open|go to|launch) instagram$",
            "^instagram$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.instagram.com"},
        "reply": "Opening Instagram",
        "compute": None,
    },
    {
        "id": "open_facebook",
        "patterns": [
            "^(open|go to|launch) facebook$",
            "^facebook$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.facebook.com"},
        "reply": "Opening Facebook",
        "compute": None,
    },
    {
        "id": "open_reddit",
        "patterns": [
            "^(open|go to|launch) reddit$",
            "^reddit$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.reddit.com"},
        "reply": "Opening Reddit",
        "compute": None,
    },
    {
        "id": "open_netflix",
        "patterns": [
            "^(open|go to|launch) netflix$",
            "^netflix$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.netflix.com"},
        "reply": "Opening Netflix",
        "compute": None,
    },
    {
        "id": "open_spotify",
        "patterns": [
            "^(open|go to|launch) spotify$",
            "^spotify$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://open.spotify.com"},
        "reply": "Opening Spotify",
        "compute": None,
    },
    {
        "id": "open_amazon",
        "patterns": [
            "^(open|go to|launch) amazon$",
            "^amazon$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.amazon.com"},
        "reply": "Opening Amazon",
        "compute": None,
    },
    {
        "id": "open_stackoverflow",
        "patterns": [
            "^(open|go to|launch) stack ?overflow$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://stackoverflow.com"},
        "reply": "Opening Stack Overflow",
        "compute": None,
    },
    {
        "id": "open_maps",
        "patterns": [
            "^(open|go to|launch) (google maps|maps)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://maps.google.com"},
        "reply": "Opening Google Maps",
        "compute": None,
    },
    {
        "id": "open_drive",
        "patterns": [
            "^(open|go to|launch) (google drive|drive)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://drive.google.com"},
        "reply": "Opening Google Drive",
        "compute": None,
    },
    {
        "id": "open_docs",
        "patterns": [
            "^(open|go to|launch) (google docs|docs)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://docs.google.com"},
        "reply": "Opening Google Docs",
        "compute": None,
    },
    {
        "id": "open_calendar",
        "patterns": [
            "^(open|go to|launch) (google calendar|calendar)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://calendar.google.com"},
        "reply": "Opening Google Calendar",
        "compute": None,
    },
    {
        "id": "open_news",
        "patterns": [
            "^(open|show me|check) (the news|google news|news)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://news.google.com"},
        "reply": "Opening Google News",
        "compute": None,
    },
    {
        "id": "open_wikipedia",
        "patterns": [
            "^(open|go to|launch) wikipedia$",
            "^wikipedia$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.wikipedia.org"},
        "reply": "Opening Wikipedia",
        "compute": None,
    },
    {
        "id": "open_leetcode",
        "patterns": [
            "^(open|go to|launch) leetcode$",
            "^leetcode$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://leetcode.com"},
        "reply": "Opening LeetCode",
        "compute": None,
    },
    {
        "id": "open_discord",
        "patterns": [
            "^(open|go to|launch) discord$",
            "^discord$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://discord.com/app"},
        "reply": "Opening Discord",
        "compute": None,
    },
    {
        "id": "open_medium",
        "patterns": [
            "^(open|go to|launch) medium$",
            "^medium$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://medium.com"},
        "reply": "Opening Medium",
        "compute": None,
    },
    {
        "id": "open_pinterest",
        "patterns": [
            "^(open|go to|launch) pinterest$",
            "^pinterest$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.pinterest.com"},
        "reply": "Opening Pinterest",
        "compute": None,
    },
    {
        "id": "play_youtube",
        "patterns": [
            "^play (.+) (on|in) youtube$",
            "^play (.+) youtube$",
            "^search youtube for (.+)$",
            "^youtube search (.+)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.youtube.com/results?search_query={group1|urlencode}"},
        "reply": "Searching YouTube for {group1}",
        "compute": None,
    },
    {
        "id": "youtube_pause",
        "patterns": [
            "^(youtube )?(pause|resume|play video)$",
            "^(pause|resume) (playback|video|music)$",
            "^(pause|resume)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "k"},
        "reply": "Toggled YouTube video playback",
        "compute": None,
    },
    {
        "id": "youtube_stop",
        "patterns": [
            "^stop (playback|music|video|song|media)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "stop"},
        "reply": "Stopping playback",
        "compute": None,
    },
    {
        "id": "youtube_fullscreen",
        "patterns": [
            "^(youtube )?(fullscreen|full screen)$",
            "^(toggle |go to )?(full ?screen|fullscreen)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "f"},
        "reply": "Toggled fullscreen",
        "compute": None,
    },
    {
        "id": "youtube_theater",
        "patterns": [
            "^(youtube )?(theater mode|theatre mode)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "t"},
        "reply": "Toggled theater mode",
        "compute": None,
    },
    {
        "id": "youtube_miniplayer",
        "patterns": [
            "^(youtube )?(mini player|miniplayer)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "i"},
        "reply": "Toggled miniplayer",
        "compute": None,
    },
    {
        "id": "youtube_mute",
        "patterns": [
            "^(youtube )?(mute|unmute)( video| sound)?$",
            "^(mute|unmute) youtube$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "m"},
        "reply": "Toggled video mute",
        "compute": None,
    },
    {
        "id": "youtube_captions",
        "patterns": [
            "^(youtube )?(captions|subtitles|toggle captions|toggle subtitles)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "c"},
        "reply": "Toggled subtitles",
        "compute": None,
    },
    {
        "id": "youtube_skip_forward",
        "patterns": [
            "^(youtube )?(skip 10 seconds|forward|skip forward|fast forward)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "l"},
        "reply": "Skipped 10 seconds forward",
        "compute": None,
    },
    {
        "id": "youtube_rewind",
        "patterns": [
            "^(youtube )?(rewind|back 10 seconds|skip back|rewind 10 seconds)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "j"},
        "reply": "Rewound 10 seconds",
        "compute": None,
    },
    {
        "id": "youtube_speed_up",
        "patterns": [
            "^(youtube )?(speed up|faster video|increase playback speed)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "shift+."},
        "reply": "Increased video speed",
        "compute": None,
    },
    {
        "id": "youtube_slow_down",
        "patterns": [
            "^(youtube )?(slow down|slower video|decrease playback speed)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "shift+,"},
        "reply": "Decreased video speed",
        "compute": None,
    },
    {
        "id": "youtube_restart",
        "patterns": [
            "^(youtube )?(restart video|start of video|replay video)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "0"},
        "reply": "Restarted video from beginning",
        "compute": None,
    },
    {
        "id": "youtube_next",
        "patterns": [
            "^(youtube )?(next video|next track|next song|skip video)$",
            "^next (track|song)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "shift+n"},
        "reply": "Playing next video",
        "compute": None,
    },
    {
        "id": "youtube_prev",
        "patterns": [
            "^(youtube )?(previous video|prev video|previous track)$",
            "^previous (track|song)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "shift+p"},
        "reply": "Playing previous video",
        "compute": None,
    },
    {
        "id": "youtube_subscriptions",
        "patterns": [
            "^(open |go to )?youtube (subscriptions|subs)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.youtube.com/feed/subscriptions"},
        "reply": "Opening YouTube Subscriptions",
        "compute": None,
    },
    {
        "id": "youtube_history",
        "patterns": [
            "^(open |go to )?youtube history$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.youtube.com/feed/history"},
        "reply": "Opening YouTube History",
        "compute": None,
    },
    {
        "id": "youtube_trending",
        "patterns": [
            "^(open |go to )?youtube trending$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.youtube.com/feed/trending"},
        "reply": "Opening YouTube Trending",
        "compute": None,
    },
    {
        "id": "youtube_library",
        "patterns": [
            "^(open |go to )?youtube (library|watch later)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.youtube.com/playlist?list=WL"},
        "reply": "Opening YouTube Watch Later",
        "compute": None,
    },
    {
        "id": "youtube_shorts",
        "patterns": [
            "^(open |go to )?youtube shorts$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.youtube.com/shorts"},
        "reply": "Opening YouTube Shorts",
        "compute": None,
    },
    {
        "id": "download_youtube_video",
        "patterns": [
            "^download (?:this|current|the)? ?(?:video|song|youtube video)(?: (.+))?$",
            "^download (.+) (?:from|on) youtube$",
        ],
        "tool": "download_media",
        "args": {"url_or_query": "{group1|default:trending song}", "media_type": "video"},
        "reply": "Starting video download to your Downloads folder in the background.",
        "compute": None,
    },
    {
        "id": "download_youtube_audio",
        "patterns": [
            "^download (?:this|current|the)? ?(?:mp3|audio)(?: (.+))?$",
            "^download audio of (.+)$",
        ],
        "tool": "download_media",
        "args": {"url_or_query": "{group1|default:trending song}", "media_type": "audio"},
        "reply": "Starting audio download to your Downloads folder in the background.",
        "compute": None,
    },
    {
        "id": "volume_up",
        "patterns": [
            "^(volume up|increase volume|louder|raise volume)$",
            "^turn up the volume$",
        ],
        "tool": "system_control",
        "args": {"action": "volume_up"},
        "reply": "Volume increased",
        "compute": None,
    },
    {
        "id": "volume_down",
        "patterns": [
            "^(volume down|decrease volume|lower volume|softer)$",
            "^turn down the volume$",
        ],
        "tool": "system_control",
        "args": {"action": "volume_down"},
        "reply": "Volume decreased",
        "compute": None,
    },
    {
        "id": "volume_max",
        "patterns": [
            "^(volume max|maximum volume|volume to 100|full volume)$",
        ],
        "tool": "system_control",
        "args": {"action": "volume_up"},
        "reply": "Volume set to maximum",
        "compute": None,
    },
    {
        "id": "volume_min",
        "patterns": [
            "^(volume min|minimum volume|lowest volume)$",
        ],
        "tool": "system_control",
        "args": {"action": "volume_down"},
        "reply": "Volume set to minimum",
        "compute": None,
    },
    {
        "id": "volume_mute",
        "patterns": [
            "^(mute|unmute|mute sound|mute volume|toggle mute)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "volumemute"},
        "reply": "Mute toggled",
        "compute": None,
    },
    {
        "id": "open_notepad",
        "patterns": [
            "^(open|launch) notepad$",
            "^notepad$",
        ],
        "tool": "open_application",
        "args": {"app_name": "notepad"},
        "reply": "Opening Notepad",
        "compute": None,
    },
    {
        "id": "open_calculator",
        "patterns": [
            "^(open|launch) calculator$",
            "^calculator$",
        ],
        "tool": "open_application",
        "args": {"app_name": "calc"},
        "reply": "Opening Calculator",
        "compute": None,
    },
    {
        "id": "open_paint",
        "patterns": [
            "^(open|launch) (paint|mspaint)$",
        ],
        "tool": "open_application",
        "args": {"app_name": "mspaint"},
        "reply": "Opening Paint",
        "compute": None,
    },
    {
        "id": "open_explorer",
        "patterns": [
            "^(open|launch) (explorer|file explorer|files|this pc|my computer)$",
        ],
        "tool": "open_application",
        "args": {"app_name": "explorer"},
        "reply": "Opening File Explorer",
        "compute": None,
    },
    {
        "id": "open_cmd",
        "patterns": [
            "^(open|launch) (command prompt|cmd|terminal)$",
        ],
        "tool": "open_application",
        "args": {"app_name": "cmd"},
        "reply": "Opening Command Prompt",
        "compute": None,
    },
    {
        "id": "open_powershell",
        "patterns": [
            "^(open|launch) powershell$",
        ],
        "tool": "open_application",
        "args": {"app_name": "powershell"},
        "reply": "Opening PowerShell",
        "compute": None,
    },
    {
        "id": "open_task_manager",
        "patterns": [
            "^(open|launch) task manager$",
        ],
        "tool": "open_application",
        "args": {"app_name": "taskmgr"},
        "reply": "Opening Task Manager",
        "compute": None,
    },
    {
        "id": "open_settings",
        "patterns": [
            "^(open|launch) (settings|windows settings)$",
        ],
        "tool": "open_application",
        "args": {"app_name": "settings"},
        "reply": "Opening Windows Settings",
        "compute": None,
    },
    {
        "id": "open_control_panel",
        "patterns": [
            "^(open|launch) control panel$",
        ],
        "tool": "open_application",
        "args": {"app_name": "control"},
        "reply": "Opening Control Panel",
        "compute": None,
    },
    {
        "id": "open_chrome",
        "patterns": [
            "^(open|launch) (chrome|google chrome)$",
        ],
        "tool": "open_application",
        "args": {"app_name": "chrome"},
        "reply": "Opening Google Chrome",
        "compute": None,
    },
    {
        "id": "open_edge",
        "patterns": [
            "^(open|launch) (edge|microsoft edge)$",
        ],
        "tool": "open_application",
        "args": {"app_name": "edge"},
        "reply": "Opening Microsoft Edge",
        "compute": None,
    },
    {
        "id": "open_vscode",
        "patterns": [
            "^(open|launch) (vs code|vscode|code)$",
        ],
        "tool": "open_application",
        "args": {"app_name": "code"},
        "reply": "Opening Visual Studio Code",
        "compute": None,
    },
    {
        "id": "open_word",
        "patterns": [
            "^(open|launch) (word|microsoft word)$",
        ],
        "tool": "open_application",
        "args": {"app_name": "word"},
        "reply": "Opening Microsoft Word",
        "compute": None,
    },
    {
        "id": "open_excel",
        "patterns": [
            "^(open|launch) (excel|microsoft excel)$",
        ],
        "tool": "open_application",
        "args": {"app_name": "excel"},
        "reply": "Opening Microsoft Excel",
        "compute": None,
    },
    {
        "id": "open_powerpoint",
        "patterns": [
            "^(open|launch) (powerpoint|power point)$",
        ],
        "tool": "open_application",
        "args": {"app_name": "powerpoint"},
        "reply": "Opening PowerPoint",
        "compute": None,
    },
    {
        "id": "close_window",
        "patterns": [
            "^(close window|close app|close this|close application|exit window)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "alt+f4"},
        "reply": None,
        "compute": None,
    },
    {
        "id": "minimize_window",
        "patterns": [
            "^(minimize|minimize window|minimize this)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "win+down"},
        "reply": "Window minimized",
        "compute": None,
    },
    {
        "id": "maximize_window",
        "patterns": [
            "^(maximize|maximize window|maximize this)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "win+up"},
        "reply": "Window maximized",
        "compute": None,
    },
    {
        "id": "show_desktop",
        "patterns": [
            "^(show desktop|go to desktop|minimize all)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "win+d"},
        "reply": "Showing desktop",
        "compute": None,
    },
    {
        "id": "switch_window",
        "patterns": [
            "^(switch window|switch app|next window)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "alt+tab"},
        "reply": "Switching window",
        "compute": None,
    },
    {
        "id": "task_view",
        "patterns": [
            "^(task view|open task view)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "win+tab"},
        "reply": "Opening Task View",
        "compute": None,
    },
    {
        "id": "lock_computer",
        "patterns": [
            "^(lock computer|lock pc|lock screen|lock windows)$",
        ],
        "tool": "system_control",
        "args": {"action": "lock_pc"},
        "reply": "Locking the workstation",
        "compute": None,
    },
    {
        "id": "take_screenshot",
        "patterns": [
            "^(take a screenshot|capture screen|screenshot|take screenshot)$",
        ],
        "tool": "system_control",
        "args": {"action": "take_screenshot"},
        "reply": "Screenshot captured.",
        "compute": None,
    },
    {
        "id": "open_action_center",
        "patterns": [
            "^(open action center|open notifications|show notifications)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "win+a"},
        "reply": "Opening Action Center",
        "compute": None,
    },
    {
        "id": "open_clipboard",
        "patterns": [
            "^(open clipboard|show clipboard|clipboard history)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "win+v"},
        "reply": "Opening Clipboard history",
        "compute": None,
    },
    {
        "id": "empty_recycle_bin",
        "patterns": [
            "^(empty recycle bin|clean recycle bin)$",
        ],
        "tool": "system_control",
        "args": {"action": "empty_recycle_bin"},
        "reply": "Recycle Bin emptied",
        "compute": None,
    },
    {
        "id": "new_tab",
        "patterns": [
            "^(new tab|open new tab)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+t"},
        "reply": "Opened new tab",
        "compute": None,
    },
    {
        "id": "close_tab",
        "patterns": [
            "^(close tab|close current tab)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+w"},
        "reply": "Closed tab",
        "compute": None,
    },
    {
        "id": "reopen_tab",
        "patterns": [
            "^(reopen tab|undo close tab|restore tab)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+shift+t"},
        "reply": "Reopened closed tab",
        "compute": None,
    },
    {
        "id": "next_tab",
        "patterns": [
            "^(next tab|switch to next tab)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+pagedown"},
        "reply": "Switched to next tab",
        "compute": None,
    },
    {
        "id": "previous_tab",
        "patterns": [
            "^(previous tab|prev tab|switch to previous tab)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+pageup"},
        "reply": "Switched to previous tab",
        "compute": None,
    },
    {
        "id": "refresh_page",
        "patterns": [
            "^(refresh|reload|refresh page|reload page)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+r"},
        "reply": "Page refreshed",
        "compute": None,
    },
    {
        "id": "bookmark_page",
        "patterns": [
            "^(bookmark page|bookmark this|add bookmark)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+d"},
        "reply": "Bookmark prompt opened",
        "compute": None,
    },
    {
        "id": "open_history",
        "patterns": [
            "^(open history|browser history|show history)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+h"},
        "reply": "Opening browser history",
        "compute": None,
    },
    {
        "id": "open_downloads",
        "patterns": [
            "^(open downloads|show downloads)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+j"},
        "reply": "Opening downloads",
        "compute": None,
    },
    {
        "id": "incognito_tab",
        "patterns": [
            "^(open incognito|new incognito window|private window)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+shift+n"},
        "reply": "Opening incognito window",
        "compute": None,
    },
    {
        "id": "zoom_in",
        "patterns": [
            "^(zoom in|make text bigger|increase zoom)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl++"},
        "reply": "Zoomed in",
        "compute": None,
    },
    {
        "id": "zoom_out",
        "patterns": [
            "^(zoom out|make text smaller|decrease zoom)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+-"},
        "reply": "Zoomed out",
        "compute": None,
    },
    {
        "id": "reset_zoom",
        "patterns": [
            "^(reset zoom|normal zoom|actual size)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+0"},
        "reply": "Zoom reset to 100%",
        "compute": None,
    },
    {
        "id": "scroll_down",
        "patterns": [
            "^(scroll down|page down)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "pagedown"},
        "reply": "Scrolled down",
        "compute": None,
    },
    {
        "id": "scroll_up",
        "patterns": [
            "^(scroll up|page up)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "pageup"},
        "reply": "Scrolled up",
        "compute": None,
    },
    {
        "id": "scroll_to_top",
        "patterns": [
            "^(scroll to top|go to top|top of page)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "home"},
        "reply": "Scrolled to top",
        "compute": None,
    },
    {
        "id": "scroll_to_bottom",
        "patterns": [
            "^(scroll to bottom|go to bottom|bottom of page)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "end"},
        "reply": "Scrolled to bottom",
        "compute": None,
    },
    {
        "id": "type_text",
        "patterns": [
            "^type (.+)$",
            "^write (.+)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "type_text", "value": "{group1}"},
        "reply": "Typed: {group1}",
        "compute": None,
    },
    {
        "id": "select_all",
        "patterns": [
            "^(select all|highlight all)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+a"},
        "reply": "Selected all",
        "compute": None,
    },
    {
        "id": "copy",
        "patterns": [
            "^(copy|copy that|copy this)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+c"},
        "reply": "Copied to clipboard",
        "compute": None,
    },
    {
        "id": "paste",
        "patterns": [
            "^(paste|paste that|paste this)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+v"},
        "reply": "Pasted",
        "compute": None,
    },
    {
        "id": "cut",
        "patterns": [
            "^(cut|cut that|cut this)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+x"},
        "reply": "Cut to clipboard",
        "compute": None,
    },
    {
        "id": "undo",
        "patterns": [
            "^(undo|undo that)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+z"},
        "reply": "Undone",
        "compute": None,
    },
    {
        "id": "redo",
        "patterns": [
            "^(redo|redo that)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+y"},
        "reply": "Redone",
        "compute": None,
    },
    {
        "id": "save_file",
        "patterns": [
            "^(save|save file|save this)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+s"},
        "reply": "Saved",
        "compute": None,
    },
    {
        "id": "find_in_page",
        "patterns": [
            "^(find|find in page|search in file)$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_hotkey", "value": "ctrl+f"},
        "reply": "Find prompt opened",
        "compute": None,
    },
    {
        "id": "press_enter",
        "patterns": [
            "^press enter$",
            "^enter$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "enter"},
        "reply": "Pressed Enter",
        "compute": None,
    },
    {
        "id": "press_space",
        "patterns": [
            "^press space$",
            "^spacebar$",
            "^space$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "space"},
        "reply": "Pressed Space",
        "compute": None,
    },
    {
        "id": "press_tab",
        "patterns": [
            "^press tab$",
            "^tab$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "tab"},
        "reply": "Pressed Tab",
        "compute": None,
    },
    {
        "id": "press_backspace",
        "patterns": [
            "^press backspace$",
            "^backspace$",
            "^delete character$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "backspace"},
        "reply": "Pressed Backspace",
        "compute": None,
    },
    {
        "id": "press_escape",
        "patterns": [
            "^press escape$",
            "^escape$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "escape"},
        "reply": "Pressed Escape",
        "compute": None,
    },
    {
        "id": "press_delete",
        "patterns": [
            "^press delete$",
            "^delete$",
        ],
        "tool": "keyboard_mouse_action",
        "args": {"action": "press_key", "value": "delete"},
        "reply": "Pressed Delete",
        "compute": None,
    },
    {
        "id": "search_google",
        "patterns": [
            "^search google for (.+)$",
            "^google search (.+)$",
            "^search for (.+)$",
            "^google (.+)$",
            "^search (.+)$",
            "^look up (.+)$",
        ],
        "tool": "web_search",
        "args": {"query": "{group1}"},
        "reply": "Searching Google for {group1}",
        "compute": None,
    },
    {
        "id": "search_wikipedia",
        "patterns": [
            "^wikipedia (.+)$",
            "^wiki (.+)$",
        ],
        "tool": "open_website",
        "args": {
            "url_or_name": "https://en.wikipedia.org/wiki/Special:Search?search={group1|urlencode}"
        },
        "reply": "Searching Wikipedia for {group1}",
        "compute": None,
    },
    {
        "id": "tell_time",
        "patterns": [
            "^(what time is it|what is the time|current time|tell me the time|time please)$",
        ],
        "tool": None,
        "args": {},
        "reply": None,
        "compute": "time",
    },
    {
        "id": "tell_date",
        "patterns": [
            "^(what is the date|today's date|what date is it|tell me the date|what's the date)$",
        ],
        "tool": None,
        "args": {},
        "reply": None,
        "compute": "date",
    },
    {
        "id": "tell_day",
        "patterns": [
            "^(what day is today|what day is it|day of the week)$",
        ],
        "tool": None,
        "args": {},
        "reply": None,
        "compute": "day",
    },
    {
        "id": "weather",
        "patterns": [
            "^weather in (.+)$",
            "^what is the weather in (.+)$",
            "^weather for (.+)$",
        ],
        "tool": "web_search",
        "args": {"query": "weather {group1}"},
        "reply": "Checking weather for {group1}",
        "compute": None,
    },
    {
        "id": "weather_general",
        "patterns": [
            "^(what is the weather|weather today|weather forecast|weather)$",
        ],
        "tool": "web_search",
        "args": {"query": "weather"},
        "reply": "Showing the current weather forecast",
        "compute": None,
    },
    {
        "id": "define_word",
        "patterns": [
            "^define (.+)$",
            "^meaning of (.+)$",
            "^what does (.+) mean$",
        ],
        "tool": "web_search",
        "args": {"query": "define {group1}"},
        "reply": "Looking up the definition of {group1}",
        "compute": None,
    },
    {
        "id": "calculate",
        "patterns": [
            "^calculate (.+)$",
            "^what is (\\d+[\\s\\d\\+\\-\\*\\/\\%\\^\\.]+)$",
        ],
        "tool": None,
        "args": {},
        "reply": None,
        "compute": "calc",
    },
    {
        "id": "tell_joke",
        "patterns": [
            "^(tell me a joke|tell a joke|joke|make me laugh)$",
        ],
        "tool": None,
        "args": {},
        "reply": None,
        "compute": "joke",
    },
    {
        "id": "flip_coin",
        "patterns": [
            "^(flip a coin|toss a coin|coin flip)$",
        ],
        "tool": None,
        "args": {},
        "reply": None,
        "compute": "coin",
    },
    {
        "id": "roll_dice",
        "patterns": [
            "^(roll a dice|roll dice|roll a die)$",
        ],
        "tool": None,
        "args": {},
        "reply": None,
        "compute": "dice",
    },
    {
        "id": "take_note",
        "patterns": [
            "^take a note (.+)$",
            "^write note (.+)$",
            "^note down (.+)$",
        ],
        "tool": "manage_notes",
        "args": {"action": "save", "content": "{group1}"},
        "reply": "Saved note: {group1}",
        "compute": None,
    },
    {
        "id": "read_notes",
        "patterns": [
            "^(read my notes|read notes|show notes|show my notes)$",
        ],
        "tool": "manage_notes",
        "args": {"action": "read"},
        "reply": None,
        "compute": None,
    },
    {
        "id": "clear_notes",
        "patterns": [
            "^(clear notes|delete notes|empty notes)$",
        ],
        "tool": "manage_notes",
        "args": {"action": "clear"},
        "reply": "Your notes have been cleared.",
        "compute": None,
    },
    {
        "id": "speed_test",
        "patterns": [
            "^(speed test|internet speed|test internet speed)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.speedtest.net"},
        "reply": "Running speed test",
        "compute": None,
    },
    {
        "id": "my_ip",
        "patterns": [
            "^(what is my ip|my ip address|show my ip)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.whatismyip.com"},
        "reply": "Checking your IP address",
        "compute": None,
    },
    {
        "id": "battery_status",
        "patterns": [
            "^(battery level|battery status|check battery|how much battery)$",
        ],
        "tool": "system_control",
        "args": {"action": "check_battery"},
        "reply": None,
        "compute": None,
    },
    {
        "id": "open_chatgpt",
        "patterns": [
            "^(open|launch|go to) chatgpt$",
            "^chatgpt$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://chatgpt.com"},
        "reply": "Opening ChatGPT",
        "compute": None,
    },
    {
        "id": "open_claude",
        "patterns": [
            "^(open|launch|go to) claude$",
            "^claude ai$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://claude.ai"},
        "reply": "Opening Claude AI",
        "compute": None,
    },
    {
        "id": "open_copilot",
        "patterns": [
            "^(open|launch|go to) copilot$",
            "^microsoft copilot$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://copilot.microsoft.com"},
        "reply": "Opening Microsoft Copilot",
        "compute": None,
    },
    {
        "id": "open_perplexity",
        "patterns": [
            "^(open|launch|go to) perplexity$",
            "^perplexity ai$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.perplexity.ai"},
        "reply": "Opening Perplexity AI",
        "compute": None,
    },
    {
        "id": "open_gemini",
        "patterns": [
            "^(open|launch|go to) (gemini|google gemini)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://gemini.google.com"},
        "reply": "Opening Google Gemini",
        "compute": None,
    },
    {
        "id": "ask_chatgpt",
        "patterns": [
            "^(ask|prompt) chatgpt (.+)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://chatgpt.com/?q={group2|urlencode}"},
        "reply": "Asking ChatGPT: {group2}",
        "compute": None,
    },
    {
        "id": "ask_perplexity",
        "patterns": [
            "^(ask|search) perplexity (.+)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://www.perplexity.ai/search?q={group2|urlencode}"},
        "reply": "Asking Perplexity AI: {group2}",
        "compute": None,
    },
    {
        "id": "ask_copilot",
        "patterns": [
            "^(ask|prompt) copilot (.+)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://copilot.microsoft.com/?q={group2|urlencode}"},
        "reply": "Asking Copilot: {group2}",
        "compute": None,
    },
    {
        "id": "ask_claude",
        "patterns": [
            "^(ask|prompt) claude (.+)$",
        ],
        "tool": "open_website",
        "args": {"url_or_name": "https://claude.ai/new"},
        "reply": "Asking Claude: {group2}",
        "compute": None,
    },
    {
        "id": "are_you_there",
        "patterns": [
            "^(are you there|you there jarvis|you there|jarvis are you there)$",
        ],
        "tool": None,
        "args": {},
        "reply": [
            "For you, sir, always.",
            "Online and fully operational! Ready for your command.",
            "Right here beside you. How can I assist?",
            "Standing by and listening!",
        ],
        "compute": None,
    },
    {
        "id": "identity",
        "patterns": [
            "^(who are you|what is your name|what's your name)$",
        ],
        "tool": None,
        "args": {},
        "reply": "I am JARVIS, your intelligent personal AI voice companion.",
        "compute": None,
    },
    {
        "id": "good_morning",
        "patterns": [
            "^good morning( jarvis)?$",
        ],
        "tool": None,
        "args": {},
        "reply": [
            "Good morning! Wishing you an energized and productive day ahead. What's on our agenda?",
            "Rise and shine! JARVIS is online and ready. How can I help you kick off the day?",
            "Good morning! All systems are optimal and ready for your commands.",
        ],
        "compute": None,
    },
    {
        "id": "good_afternoon",
        "patterns": [
            "^good afternoon( jarvis)?$",
        ],
        "tool": None,
        "args": {},
        "reply": [
            "Good afternoon! Hope everything is progressing smoothly. What would you like to do next?",
            "Good afternoon! Ready when you are.",
        ],
        "compute": None,
    },
    {
        "id": "good_evening",
        "patterns": [
            "^good evening( jarvis)?$",
        ],
        "tool": None,
        "args": {},
        "reply": [
            "Good evening! Time to wind down or wrap up some tasks. How can I assist you?",
            "Good evening! I hope you've had a satisfying day.",
        ],
        "compute": None,
    },
    {
        "id": "good_night",
        "patterns": [
            "^good night( jarvis)?$",
        ],
        "tool": None,
        "args": {},
        "reply": [
            "Good night! Rest well and recharge. I'll be here when you return.",
            "Good night! Standing by in low-power idle.",
        ],
        "compute": None,
    },
    {
        "id": "how_are_you",
        "patterns": [
            "^(how are you|how are you doing|how is it going|how do you feel|how was your day)$",
        ],
        "tool": None,
        "args": {},
        "reply": [
            "I am functioning at 100% efficiency and feeling fantastic! How about you?",
            "All systems are green and running smoothly! What's on your mind today?",
            "Never better! Ready to tackle whatever you have in mind.",
        ],
        "compute": None,
    },
    {
        "id": "compliment_me",
        "patterns": [
            "^(compliment me|say something nice|praise me)$",
        ],
        "tool": None,
        "args": {},
        "reply": [
            "You have great vision, incredible determination, and you're doing amazing work today!",
            "You're sharp, resourceful, and capable of solving any challenge. Keep going!",
            "It's genuinely a pleasure working with you. You make things happen!",
        ],
        "compute": None,
    },
    {
        "id": "bored",
        "patterns": [
            "^(i am bored|i'm bored|feeling bored)$",
        ],
        "tool": None,
        "args": {},
        "reply": [
            "Boredom is just waiting for a spark! Would you like me to play some music on YouTube, tell an interesting fact, or test your internet speed?",
            "How about exploring something new? I can find a great video on YouTube, tell you a joke, or we can look up a fascinating topic!",
        ],
        "compute": None,
    },
    {
        "id": "tell_quote",
        "patterns": [
            "^(tell me a quote|inspire me|motivate me|quote of the day)$",
        ],
        "tool": None,
        "args": {},
        "reply": [
            "'The secret of getting ahead is getting started.' — Mark Twain",
            "'It always seems impossible until it's done.' — Nelson Mandela",
            "'The best way to predict the future is to invent it.' — Alan Kay",
            "'Success is not final, failure is not fatal: it is the courage to continue that counts.' — Winston Churchill",
        ],
        "compute": None,
    },
    {
        "id": "tell_fact",
        "patterns": [
            "^(tell me a fact|interesting fact|fun fact|random fact)$",
        ],
        "tool": None,
        "args": {},
        "reply": [
            "Did you know? Honey never spoils — archaeologists have found edible honey in ancient Egyptian tombs that is over 3,000 years old!",
            "Did you know? The first computer programmer in history was Ada Lovelace in the 1840s.",
            "Did you know? Octopuses have three hearts and their blood is blue!",
            "Did you know? The world's first webcam was created at Cambridge University to check the status of a coffee pot!",
        ],
        "compute": None,
    },
    {
        "id": "cheer_me_up",
        "patterns": [
            "^(cheer me up|make me happy|i feel sad)$",
        ],
        "tool": None,
        "args": {},
        "reply": [
            "Take a deep breath. You've handled 100% of difficult days so far, and today is another victory waiting for you!",
            "No matter how tough things feel, you have the resilience to overcome it. I'm right here with you!",
            "Remember: Even the darkest night will end and the sun will rise. You've got this!",
        ],
        "compute": None,
    },
    {
        "id": "thanks",
        "patterns": [
            "^(thank you|thanks|thanks a lot|thank you so much)$",
        ],
        "tool": None,
        "args": {},
        "reply": [
            "You are very welcome! Always happy to assist.",
            "Anytime! Let me know if there's anything else you need.",
            "My pleasure, sir!",
        ],
        "compute": None,
    },
    {
        "id": "help_commands",
        "patterns": [
            "^(help|what can you do|show commands|list commands|available commands)$",
        ],
        "tool": None,
        "args": {},
        "reply": "I can open applications, control YouTube playback and downloads, prompt ChatGPT and Copilot, locate files in File Explorer, manage volume, and much more. Check VOICE_COMMANDS.md for details.",
        "compute": None,
    },
    {
        "id": "exit",
        "patterns": [
            "^(exit|quit|stop assistant|goodbye|bye|close assistant)$",
        ],
        "tool": None,
        "args": {},
        "reply": "Goodbye! Have a great day.",
        "compute": None,
    },
]

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "There are 10 types of people in the world: those who understand binary, and those who don't.",
    "Why did the computer go to the doctor? Because it had a virus!",
    "What is a programmer's favorite hangout spot? The Foo Bar.",
    "A SQL statement walks into a bar, approaches two tables, and asks: May I join you?",
    "Why was the JavaScript developer sad? Because they didn't Node how to Express themselves!",
    "What did one computer say to the other? Between 0 and 1, you're my favorite.",
]
