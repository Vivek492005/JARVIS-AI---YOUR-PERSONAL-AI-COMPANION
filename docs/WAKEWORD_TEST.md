# Wake-word test procedure (Task 3.2)

Targets: **< 1 false accept/hour**, **>= 95% detection over 50 attempts**.
Run on the real machine — this VM has no mic.

## False-accept test (1 hour)

1. `settings.toml`: `wakeword_threshold = 0.5` (the value under test).
2. Play 1 hour of mixed audio through speakers at normal volume:
   TV shows, YouTube, news — **no one saying "jarvis"**.
3. Count `WakeDetected` events: `jarvis doctor` shows the mic log, or
   grep the JSONL audit log for wake events.
4. **Pass:** 0 false wakes. 1 = borderline (raise threshold to 0.6 and
   re-run). 2+ = fail (try the other backend or retrain).

Note the `aec_mode`: run once with `ducking` (default) while JARVIS
speaks periodically — self-triggering counts as false accepts.

## False-reject test (50 attempts)

1. Quiet room, normal speaking voice, 1–2 m from the mic.
2. Say "hey jarvis" 50 times, ~5 s apart. Vary slightly: "jarvis",
   "hey JARVIS", fast/slow.
3. Count detections (earcon + HUD state change each time).
4. **Pass:** >= 48/50 (96%). Below that: lower the threshold to 0.4 or
   switch backends, then re-run *both* tests (threshold trades one
   metric against the other).

## Follow-up window check

1. Trigger the wake word, get a response.
2. Within 7 s, speak a command **without** the wake word → should work.
3. Wait 10 s, speak again without it → should be ignored.

## Recording results

Append to this file:

| Date | Backend | Threshold | False accepts/hr | Detects/50 | Notes |
|---|---|---|---|---|---|
| _pending_ | | | | | |
