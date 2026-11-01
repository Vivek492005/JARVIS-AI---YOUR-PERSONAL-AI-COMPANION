# XTTS v2 local voice setup (Task 3.6 extra)

XTTS v2 (Coqui) is the fully-offline, no-API-key TTS tier: it runs on
your machine, never exhausts a quota, and can **clone a voice** from a
~6 second sample — the most human-like free option.

## Install

```powershell
pip install jarvis-assistant[xtts]
```

This pulls `coqui-tts` (~500 MB package). The model itself
(`tts_models/multilingual/multi-dataset/xtts_v2`, ~2 GB) downloads on
first synth into the TTS cache dir. Needs a GPU for real-time; CPU works
but is ~2-4x slower than real-time for long sentences (fine for short
replies).

## Speaker reference WAV

1. Record ~6 seconds of clean speech (16 kHz mono WAV is ideal; the
   engine resamples anyway).
2. Point config at it:

```toml
[voice]
tts_engine = "xtts"
xtts_speaker_wav = "C:\\Users\\you\\jarvis-voice.wav"
xtts_language = "en"   # "en" handles Latin-script Hinglish best
```

Tips for a good clone: quiet room, natural pace, no background music.
Your own voice works — JARVIS literally sounds like you.

## Behavior notes

- First synth is slow (model load, 10-30 s); later ones reuse the model.
- `jarvis doctor` reports whether coqui-tts is installed.
- Privacy Mode treats XTTS as local (no cloud egress).
- If the WAV path is missing, the engine raises a clear error instead of
  falling back silently — check the path.
