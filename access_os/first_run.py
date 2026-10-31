"""
first_run.py — One-time API key setup for non-technical users.

The packaged installer (Plan 03) must not ask users to hand-edit a `.env`
file. On launch, main.py calls ensure_api_keys() BEFORE the voice engine is
constructed:

* If any LLM key is already present (environment or .env), return silently.
* Otherwise show a small GUI dialog: paste up to 3 keys -> writes .env ->
  sets os.environ so this process picks them up immediately.
* If the user skips/closes, JARVIS still starts — the offline fallback
  engine keeps basic commands working.

Only stdlib (tkinter) is used so this works inside the PyInstaller bundle.
"""

import os

# NOTE: tkinter is imported lazily inside ensure_api_keys() so that importing
# this module never fails on machines without a Tk build. Only stdlib is used.

# (env var, label shown in the dialog, free-tier hint)
KEY_FIELDS = [
    ("HUGGINGFACE_API_KEY",
     "Hugging Face token",
     "free at huggingface.co/settings/tokens — main AI brain"),
    ("DEEPSEEK_API_KEY",
     "DeepSeek key (optional)",
     "backup brain if Hugging Face is down"),
    ("RUMIK_API_KEY",
     "Rumik key (optional)",
     "premium human-like voice (falls back to free voices)"),
]

ENV_FILE = ".env"


def _any_key_present() -> bool:
    return any(os.getenv(name) for name, _, _ in KEY_FIELDS)


def _write_env_file(values: dict):
    """Merge new keys into .env (create it if missing), preserving the rest."""
    existing = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            existing = f.readlines()
    existing = [ln for ln in existing
                if not any(ln.startswith(f"{k}=") for k in values)]
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(existing)
        if existing and not existing[-1].endswith("\n"):
            f.write("\n")
        for key, val in values.items():
            if val:
                f.write(f"{key}={val}\n")
                os.environ[key] = val  # pick up immediately in this process


def ensure_api_keys() -> bool:
    """Show the first-run dialog if no LLM key is configured.

    Returns True if keys are now available (or were already), False if the
    user skipped. Never raises — JARVIS must start regardless.
    """
    if _any_key_present():
        return True
    try:
        import tkinter as tk
        root = tk.Tk()
    except Exception:
        return False  # headless / no display server / no Tk build

    root.title("Welcome to JARVIS — one-time setup")
    root.resizable(False, False)
    saved = {"ok": False}

    tk.Label(root, text="Paste your API keys to unlock the full AI brain.\n"
                        "All three services have a free tier. You can skip —\n"
                        "basic voice commands still work offline.",
             justify="left", padx=16, pady=12).pack()

    entries = {}
    for name, label, hint in KEY_FIELDS:
        frame = tk.Frame(root, padx=16, pady=4)
        frame.pack(fill="x")
        tk.Label(frame, text=label, width=24, anchor="w").pack(side="top", anchor="w")
        entry = tk.Entry(frame, show="•", width=52)
        entry.pack(side="top", fill="x")
        tk.Label(frame, text=hint, fg="gray", anchor="w").pack(side="top", anchor="w")
        entries[name] = entry

    btn_frame = tk.Frame(root, pady=12)
    btn_frame.pack()

    def _save():
        values = {name: entry.get().strip() for name, entry in entries.items()}
        try:
            _write_env_file(values)
        except Exception:
            pass
        saved["ok"] = _any_key_present()
        root.destroy()

    def _skip():
        root.destroy()

    tk.Button(btn_frame, text="Save & Start JARVIS", command=_save,
              padx=12, pady=4).pack(side="left", padx=8)
    tk.Button(btn_frame, text="Skip for now", command=_skip,
              padx=12, pady=4).pack(side="left", padx=8)

    # Center on screen
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    root.geometry(f"+{(root.winfo_screenwidth() - w) // 2}+{(root.winfo_screenheight() - h) // 2}")
    root.mainloop()
    return saved["ok"]
