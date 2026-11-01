# Audio setup (Tasks 3.1–3.3)

All audio backends are **optional extras** — the base install never
touches audio hardware, and every backend raises a clear error telling
you the exact `pip install` when it's missing.

## Install

```powershell
# capture + VAD basics
pip install jarvis-assistant[audio]      # sounddevice, webrtcvad

# wake word
pip install jarvis-assistant[wakeword]   # openwakeword

# local STT (offline tier)
pip install jarvis-assistant[voice-local]  # faster-whisper, silero-vad

# local neural TTS / voice cloning
pip install jarvis-assistant[xtts]       # coqui-tts (~2 GB model)
```

## Device selection

```powershell
jarvis doctor            # lists input devices under "audio"
```

Then pin one in `settings.toml`:

```toml
[voice]
input_device = 2         # index from the doctor listing; empty = default
sample_rate = 16000
```

Hot-plug: restart capture (`AudioCapture.stop()` / `start()`); device
indexes can shift when USB devices come and go — prefer the default
device unless you have a reason not to.

## Echo (the mic hears our own speakers)

Pick one in `settings.toml`:

```toml
[voice]
aec_mode = "ducking"     # default: raise wake-word threshold while TTS plays
# aec_mode = "headset"   # you promise a headset; no software action
# aec_mode = "webrtc"    # real AEC; needs a backend (below)
```

Real AEC (`webrtc` mode) needs a native backend — options:
- **speexdsp** (`pip install speexdsp`): `SpeexEchoCanceller`, wire its
  `process(mic_frame, reference_frame)` into
  `EchoGuard.register_aec_backend`.
- **WebRTC APM** via `webrtc-audio-processing` bindings (heavier).

Until a backend registers, `webrtc` mode raises a clear error rather
than silently doing nothing.

## Noise suppression

```toml
[voice]
noise_suppression = false   # RNNoise etc. — measure WER before/after first
```

The plan's rule: keep it only if the STT bake-off (`evals/stt/`) shows a
WER improvement. No backend is bundled; plug any frame-wise denoiser
into `AudioCapture(on_frame=...)`.

## Wake word backends

- **openwakeword** (default): `pip install jarvis-assistant[wakeword]`.
  Ships a `hey_jarvis` model; train custom words with openWakeWord's
  notebooks and point `wakeword_model_paths` at them.
- **porcupine**: `pip install pvporcupine`, then store a free-tier
  Picovoice access key: `python -m jarvis.core.secrets store PORCUPINE_KEY`
  and set `wakeword_backend = "porcupine"`.

## Troubleshooting

- "No input devices": check Windows Settings → Sound → Input, and that
  no other app holds the mic exclusively.
- Choppy audio: raise `frame_ms` to 30; close apps that resample the mic.
- Self-triggering: switch `aec_mode` to `headset`, or raise
  `wakeword_threshold` toward 0.7.
