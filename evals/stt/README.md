# STT bake-off test set (Task 3.4)

Record **100 utterances** on the real machine (laptop mic + headset, quiet
+ noisy room):

- **40 Hinglish** — e.g. "bhai chrome khol aur latest AI news search kar",
  "volume thoda badha de", "yeh file downloads folder mein dhoondh"
- **30 Hindi** — e.g. "samay kya ho raha hai", "kal ka mausam batao"
- **30 English** — e.g. "open spotify and play something", "take a screenshot"

Include app/brand names (Chrome, VS Code, Spotify, LeetCode), numbers
("set a timer for 5 minutes"), and code-switched sentences.

## Layout

```
evals/stt/
  wavs/<id>.wav        # 16 kHz mono PCM WAVs, <id> = hing_001, hin_001, eng_001...
  manifest.jsonl       # one JSON per line:
                       # {"id": "hing_001", "ref": "<exact transcript>",
                       #  "lang": "hi-en", "intent": "open_application:chrome"}
  fixtures/            # synthetic smoke-test fixtures (this VM)
```

`intent` is the expected reflex-router tool (`tool_name`, e.g.
`open_application`, `web_search`, `system_control`) — used for the
command-intent accuracy column. Write reference transcripts yourself;
don't generate them with an STT engine (that would bias the bake-off).

## Running

```bash
python evals/stt/stt_bakeoff.py \
  --engines google,faster-whisper:large-v3,sarvam,deepgram \
  --manifest evals/stt/manifest.jsonl
# -> evals/reports/stt_YYYY-MM-DD.csv
```

Cloud engines need their keys in secrets (`SARVAM_API_KEY`,
`DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`) — never in the manifest.

## Decision rule (plan)

primary = max(intent accuracy) subject to p50 latency ≤ 600 ms;
local fallback = best offline engine. Record the outcome in
`docs/DECISION_STT.md`.
