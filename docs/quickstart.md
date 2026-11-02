# Quickstart (5 minutes)

!!! note "Until v1.0.0"
    The Windows installer doesn't exist yet — it's built by the
    `v1.0.0` tag on real hardware. These steps run JARVIS from source
    on any machine with Python 3.11+.

## 1. Install

```bash
git clone https://github.com/Vivek492005/JARVIS-AI---YOUR-PERSONAL-AI-COMPANION
cd JARVIS-AI---YOUR-PERSONAL-AI-COMPANION
pip install -r requirements.txt
```

## 2. First run

```bash
python -m jarvis onboard   # 8-step wizard: mic, wake word, keys, privacy
python -m jarvis doctor    # diagnostics — everything should be green
```

## 3. Talk to it

```bash
python -m jarvis serve     # start the service (another terminal:)
python -m jarvis send "volume up"
```

With autonomy level 1 (the default), read-only actions run immediately and
everything else asks first. Say **"haan"** to confirm, **"nahi"** to cancel.

## 4. Make it yours

- `settings.toml` — wake word, voice, autonomy level (0–3)
- `workspace/PERSONA.md` — tone and style (can't override safety rules)
- `python -m jarvis skill list` — bundled skills

## Next

- [Architecture](architecture.md) — what runs where
- [Voice setup](AUDIO_SETUP.md) — mic tuning, Hinglish tips
- [FAQ](faq.md) — troubleshooting
