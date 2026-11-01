# Voice framework decision (Task 3.11): build vs adopt Pipecat

**Verdict: KEEP CUSTOM (defer Pipecat adoption).** Revisit in Phase 9
if WebRTC transport is needed.

## What Pipecat gives you (researched Nov 2026)

Pipecat (Daily.co, open-source) is the canonical Python orchestrator for
real-time voice agents: VAD → STT → LLM → TTS as a frame-based pipeline,
with built-in barge-in interruption, turn detection (smart-turn),
and ~20-line voice agents from prefab STT/LLM/TTS services. Sources:
the Pipecat pipeline pattern is widely documented as the fastest path to
a barge-in-capable voice loop in Python.

## Why we still keep our custom pipeline

1. **The spike criterion is already met by custom code.** The plan said:
   adopt only if barge-in/latency come "without custom code". We have now
   built both natively: `voice/vad.py` (Silero/webrtc/energy + semantic
   endpointing), `voice/bargein.py` (250 ms stop budget, duck-aware),
   `voice/dialogue.py` (state machine), `voice/latency.py` (budget +
   `jarvis doctor --latency`). Adopting Pipecat now would *replace*
   working, tested code instead of filling a gap.

2. **Architecture mismatch.** Pipecat is asyncio-first (PipelineRunner,
   frame processors on an event loop). Our runtime is deliberately
   **threading-based** (Task 2.3 decision: sync Bus + LaneQueue, worker
   threads). Adopting Pipecat means rewriting the runtime seam — a
   Phase-2-scale refactor for no functional gain today.

3. **Our moat is the safety layer, not the transport.** Policy engine
   (L0–L3), tool registry with risk tiers, reflex gating, audit log,
   kill switch, prompt-injection containment — none of this exists in
   Pipecat. Even with Pipecat, every tool call would still route through
   our gate. The orchestration is the *commodity* part; the safety is
   the *differentiator*. Keep the differentiator native.

4. **No WebRTC need yet.** Pipecat's transport story (Daily/WebRTC)
   matters for telephony and browser clients. JARVIS v1.0 is a local
   Windows app: mic + speakers via sounddevice. If a remote/mobile
   client needs WebRTC later, that's a Phase 9 moonshot with a clear
   seam (`voice/audio.py: AudioSource`).

## What we take from Pipecat anyway

- **Frame-based thinking**: our partial/final transcription events and
  per-sentence TTS chunks mirror Pipecat's frame model.
- **smart-turn semantics**: our connector-word hangover extension
  (3.3) is the same idea as dynamic endpointing — acknowledged here.
- **Benchmark**: Pipecat's ~600 ms voice-to-voice budget matches our
  latency table (3.10); we measure against it.

## Revisit triggers

- WebRTC/browser client requirement (Phase 9).
- Our barge-in false-trigger rate proves unfixable without a turn model
  (then: adopt Pipecat's turn analyzer as a *component*, not the framework).
- Team grows and asyncio expertise arrives.
