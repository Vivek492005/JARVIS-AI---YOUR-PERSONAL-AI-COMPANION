# STT bake-off decision (Task 3.4) — PROVISIONAL

**Status:** provisional. No real benchmark has been run yet — the bake-off
needs 100 hand-recorded utterances on real hardware (see
`evals/stt/README.md`). The harness (`evals/stt/stt_bakeoff.py`) is ready;
re-run it on Vivek's machine and replace this note with measured numbers.

## Candidates and what we know today

| Engine | Type | Hinglish evidence | Cost | Offline | Streaming |
|---|---|---|---|---|---|
| `google` (current) | Cloud | Decent on hi-IN; no key needed | Free | No | No |
| `faster-whisper` large-v3 | Local | Stock ~30 WER on code-switched speech (plan refs) | Free | Yes | Partial |
| Hinglish-tuned Whisper ckpt | Local | Community cards claim ~11-14 WER | Free | Yes | Partial |
| `sarvam` (Saaras) | Cloud | Indic specialist, vendor streaming claims | Key+quota | No | Yes |
| `deepgram` (Nova-3) | Cloud | Best code-switching in one 3rd-party report | Key+quota | No | Yes |
| `scribe` (ElevenLabs) | Cloud | Lowest WER in one Indian-language report | Key+quota | No | No |

## Provisional pick (until measured)

- **Default:** `google` — zero setup, free, no key to exhaust. Unchanged
  behavior from v0.4.0.
- **Privacy Mode / offline:** `faster-whisper` (large-v3, or a
  Hinglish-tuned checkpoint via `model_path` when one is validated).
- **Opt-in streaming upgrade:** `sarvam` or `deepgram` once the bake-off
  shows intent-accuracy ≥ 90% at p50 ≤ 600 ms.

## Decision rule (binding when data exists)

primary = max(intent accuracy) s.t. p50 latency ≤ 600 ms;
local fallback = best offline engine. Write the CSV to
`evals/reports/stt_YYYY-MM-DD.csv` and update this doc.

## Script handling

Transcripts stay in **Latin (romanized) Hinglish** as the canonical form
for the LLM prompt; Devanagari is normalized at the STT boundary when a
provider returns it. Rationale: the reflex rules and prompts are all
Latin-script today; mixing scripts would halve rule coverage.
