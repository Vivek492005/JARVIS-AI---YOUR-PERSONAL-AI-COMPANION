# Telemetry — Task 8.8

## Current state: there is none

JARVIS ships **zero telemetry**. No analytics SDK, no phone-home, no usage
ping. The update checker (`core/updater.py`) only contacts GitHub when the
user asks it to check, and crash reports stay in `~/.jarvis/crashes/`
unless upload is explicitly opted in.

## If telemetry is ever added, these are the rules

1. **Opt-in only.** Default off. The onboarding wizard asks once, plainly.
2. **Aggregated, never content.** Counts and timings (e.g. "reflex hit
   rate"), never transcripts, commands, file names, or screen contents.
3. **Documented.** Exactly what's collected lives in this file, with the
   code that collects it linked.
4. **Deletable.** One command wipes everything collected.
5. **No third-party trackers.** Self-hosted endpoint only.

Any telemetry PR that violates these gets rejected on sight.
