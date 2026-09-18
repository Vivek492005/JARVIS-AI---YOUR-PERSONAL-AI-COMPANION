"""
JARVIS GUI - Cute Puppy AI Companion Widget
Built with Tkinter + Pillow for instant startup with zero external C++ dependencies.
Features:
- Frameless, floating, always-on-top companion card
- Draggable from anywhere on the widget
- Rounded cute puppy avatar
- Real-time listening indicator, user query display, and assistant response bubble
- Mic On/Off toggle button & one-click exit button
- Thread-safe updates from speech recognition and TTS threads
"""

import os
import sys
import queue
import logging
import threading
import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageTk, ImageDraw

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
AVATAR_PATH = os.path.join(_HERE, "puppy.jpg")


class JARVISGUI:
    """Cute floating AI companion widget for JARVIS."""

    def __init__(self, assistant_controller):
        self.assistant = assistant_controller
        self.is_listening = True
        self.queue = queue.Queue()

        self._init_window()
        self._load_avatar()
        self._build_widgets()
        self._setup_dragging()
        self._start_queue_poller()

    # ── Window Setup ─────────────────────────────────────────────────────────

    def _init_window(self):
        self.root = tk.Tk()
        self.root.title("JARVIS Companion")
        self.root.overrideredirect(True)  # Frameless
        self.root.wm_attributes("-topmost", True)  # Always on top

        # Set default size and position (bottom-right above taskbar)
        self.width = 300
        self.height = 420
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = screen_w - self.width - 40
        pos_y = screen_h - self.height - 80
        self.root.geometry(f"{self.width}x{self.height}+{pos_x}+{pos_y}")

        # Dark theme palette
        self.bg_color = "#1E1E2E"       # Deep dark slate
        self.card_border = "#89B4FA"    # Soft blue accent border
        self.text_primary = "#CDD6F4"   # Soft white/lavender
        self.text_secondary = "#BAC2DE" # Subtle grey-blue
        self.accent_green = "#A6E3A1"   # Mint green (active)
        self.accent_pink = "#F38BA8"    # Soft coral/red (danger/mute)
        self.btn_bg = "#313244"         # Elevated surface

        self.root.configure(bg=self.card_border)

        # Main inner container creating a 2px accent border around the card
        self.container = tk.Frame(self.root, bg=self.bg_color, padx=16, pady=16)
        self.container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

    # ── Avatar Handling ──────────────────────────────────────────────────────

    def _load_avatar(self):
        """Load and create a rounded version of puppy.jpg."""
        size = 145
        self.avatar_image = None
        if os.path.exists(AVATAR_PATH):
            try:
                img = Image.open(AVATAR_PATH).convert("RGBA")
                img = img.resize((size, size), Image.Resampling.LANCZOS)

                # Create smooth rounded corners mask
                mask = Image.new("L", (size, size), 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle((0, 0, size, size), radius=28, fill=255)
                img.putalpha(mask)

                self.avatar_image = ImageTk.PhotoImage(img)
            except Exception as e:
                logger.error(f"Failed to load puppy avatar: {e}")

    # ── Widget Layout ────────────────────────────────────────────────────────

    def _build_widgets(self):
        # 1. Avatar display
        if self.avatar_image:
            self.avatar_label = tk.Label(
                self.container,
                image=self.avatar_image,
                bg=self.bg_color
            )
        else:
            self.avatar_label = tk.Label(
                self.container,
                text="🐶",
                font=("Segoe UI Emoji", 44),
                bg=self.bg_color,
                fg=self.text_primary
            )
        self.avatar_label.pack(pady=(4, 6))

        # 2. Status Badge (Listening... / Paused)
        self.status_label = tk.Label(
            self.container,
            text="● Listening...",
            font=("Segoe UI", 9, "bold"),
            bg=self.bg_color,
            fg=self.accent_green
        )
        self.status_label.pack(pady=(0, 4))

        # 3. User spoken command label
        self.user_label = tk.Label(
            self.container,
            text="Say something…",
            font=("Segoe UI", 10, "italic"),
            bg=self.bg_color,
            fg=self.text_secondary,
            wraplength=260,
            justify=tk.CENTER
        )
        self.user_label.pack(pady=(2, 4))

        # 4. Assistant response bubble
        self.assistant_label = tk.Label(
            self.container,
            text="Hi! I'm JARVIS. 🐾",
            font=("Segoe UI", 11, "bold"),
            bg=self.bg_color,
            fg=self.card_border,
            wraplength=260,
            justify=tk.CENTER
        )
        self.assistant_label.pack(pady=(4, 6))

        # 5. Quick Command Entry Box
        self.input_frame = tk.Frame(self.container, bg=self.btn_bg, padx=4, pady=3)
        self.input_frame.pack(fill=tk.X, pady=(2, 6))

        self.cmd_entry = tk.Entry(
            self.input_frame,
            font=("Segoe UI", 9),
            bg=self.btn_bg,
            fg=self.text_primary,
            insertbackground=self.text_primary,
            relief=tk.FLAT,
            bd=0
        )
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 2))
        self.cmd_entry.bind("<Return>", lambda event: self._on_submit_text())

        self.send_btn = tk.Button(
            self.input_frame,
            text="➔",
            font=("Segoe UI", 9, "bold"),
            bg=self.card_border,
            fg="#11111B",
            activebackground="#b4befe",
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=1,
            cursor="hand2",
            command=self._on_submit_text
        )
        self.send_btn.pack(side=tk.RIGHT)

        # 6. Bottom controls row
        self.controls_frame = tk.Frame(self.container, bg=self.bg_color)
        self.controls_frame.pack(fill=tk.X, pady=(4, 0))

        # Mic toggle button
        self.mic_btn = tk.Button(
            self.controls_frame,
            text="🎤  Mic On",
            font=("Segoe UI", 10, "bold"),
            bg=self.btn_bg,
            fg=self.accent_green,
            activebackground="#45475A",
            activeforeground=self.accent_green,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.toggle_mic
        )
        self.mic_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))

        # Close button
        self.close_btn = tk.Button(
            self.controls_frame,
            text="✖",
            font=("Segoe UI", 10, "bold"),
            bg=self.accent_pink,
            fg="#11111B",
            activebackground="#eba0ac",
            activeforeground="#11111B",
            relief=tk.FLAT,
            bd=0,
            width=3,
            pady=6,
            cursor="hand2",
            command=self.close_app
        )
        self.close_btn.pack(side=tk.RIGHT)

    def _on_submit_text(self):
        """Submit text command to assistant."""
        query = self.cmd_entry.get().strip()
        if query:
            self.cmd_entry.delete(0, tk.END)
            if self.assistant and hasattr(self.assistant, "send_text_command"):
                self.assistant.send_text_command(query)

    # ── Window Dragging ──────────────────────────────────────────────────────

    def _setup_dragging(self):
        """Allow dragging the window by clicking on the background or labels."""
        self._drag_data = {"x": 0, "y": 0}

        def on_drag_start(event):
            self._drag_data["x"] = event.x_root - self.root.winfo_x()
            self._drag_data["y"] = event.y_root - self.root.winfo_y()

        def on_drag_motion(event):
            new_x = event.x_root - self._drag_data["x"]
            new_y = event.y_root - self._drag_data["y"]
            self.root.geometry(f"+{new_x}+{new_y}")

        # Bind to background and labels so user can grab anywhere
        for widget in (self.root, self.container, self.avatar_label, self.status_label, self.user_label, self.assistant_label):
            widget.bind("<Button-1>", on_drag_start)
            widget.bind("<B1-Motion>", on_drag_motion)

    # ── Thread-Safe Signal Queue ─────────────────────────────────────────────

    def _start_queue_poller(self):
        """Process UI update requests from background threads every 40ms."""
        try:
            while not self.queue.empty():
                action, payload = self.queue.get_nowait()
                if action == "status":
                    self.status_label.config(text=payload)
                    if "Paused" in payload:
                        self.status_label.config(fg=self.accent_pink)
                    else:
                        self.status_label.config(fg=self.accent_green)
                elif action == "user":
                    self.user_label.config(text=f'"{payload}"')
                elif action == "assistant":
                    self.assistant_label.config(text=payload)
        except Exception as e:
            logger.error(f"Error in queue poller: {e}")

        # Poll again in 40ms
        self.root.after(40, self._start_queue_poller)

    def set_status(self, text: str):
        self.queue.put(("status", text))

    def set_user_text(self, text: str):
        self.queue.put(("user", text))

    def set_assistant_text(self, text: str):
        self.queue.put(("assistant", text))

    # ── Button Handlers ──────────────────────────────────────────────────────

    def toggle_mic(self):
        """Toggle speech listening state."""
        if self.is_listening:
            self.is_listening = False
            self.mic_btn.config(text="🔇  Mic Off", fg=self.accent_pink)
            self.set_status("○ Paused")
            if self.assistant:
                try:
                    self.assistant.voice.stop_listening()
                except Exception as e:
                    logger.error(f"Error pausing voice: {e}")
        else:
            self.is_listening = True
            self.mic_btn.config(text="🎤  Mic On", fg=self.accent_green)
            self.set_status("● Listening...")
            if self.assistant:
                try:
                    self.assistant.voice.start_listening(callback=self.assistant.on_voice_command)
                except Exception as e:
                    logger.error(f"Error resuming voice: {e}")

    def close_app(self):
        """Gracefully shut down assistant and close UI."""
        self.set_status("Shutting down…")

        def _do_shutdown():
            if self.assistant:
                try:
                    self.assistant.stop()
                except Exception as e:
                    logger.error(f"Shutdown error: {e}")
            self.root.after(50, self.root.destroy)

        threading.Thread(target=_do_shutdown, daemon=True).start()

    def show(self):
        """Start the Tkinter event loop."""
        self.root.mainloop()
