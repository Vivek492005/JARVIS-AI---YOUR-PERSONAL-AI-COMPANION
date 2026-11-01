"""STT bake-off runner (Master Plan Task 3.4).

Runs every configured STT engine over the same WAV test set and writes a
CSV report with WER, command-intent accuracy, and latency percentiles.

Test-set layout (see evals/stt/README.md):
    evals/stt/wavs/<id>.wav
    evals/stt/manifest.jsonl   # {"id": ..., "ref": "...", "intent": "open_application:chrome"}

Usage:
    python evals/stt/stt_bakeoff.py --engines google,faster-whisper:medium \\
        --manifest evals/stt/manifest.jsonl --out evals/reports/stt_$(date +%F).csv

Needs real hardware + real utterances; on this VM it runs against the
synthetic fixtures in evals/stt/fixtures/ (smoke test only).
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from jarvis.voice.stt import make_engine  # noqa: E402


def wer(ref: str, hyp: str) -> float:
    """Word error rate (simple, dependency-free)."""
    r, h = ref.lower().split(), hyp.lower().split()
    if not r:
        return 0.0 if not h else 1.0
    # Levenshtein on word sequences.
    prev = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        cur = [i]
        for j, hw in enumerate(h, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (0 if rw == hw else 1)))
        prev = cur
    return prev[len(h)] / len(r)


def intent_of(text: str) -> str:
    """Command-intent accuracy probe: which tool would the reflex router pick?"""
    try:
        from jarvis.brain.reflex import match_command
        m = match_command(text)
        return m.tool_name if m else "<none>"
    except Exception:
        return "<router-unavailable>"


def run(manifest_path: str, engines: list, out_path: str) -> None:
    rows = []
    with open(manifest_path, encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]
    base = os.path.dirname(manifest_path)
    for eng_name in engines:
        try:
            engine = make_engine(eng_name)
        except Exception as e:
            print(f"[skip] {eng_name}: {e}")
            continue
        wers, lats, intent_ok = [], [], 0
        for it in items:
            wav = os.path.join(base, "wavs", it["id"] + ".wav")
            if not os.path.exists(wav):
                print(f"[skip] missing wav {wav}")
                continue
            with open(wav, "rb") as fh:
                # strip 44-byte WAV header -> raw PCM
                pcm = fh.read()[44:]
            t = engine.transcribe(pcm, language=it.get("lang", "hi-en"))
            wers.append(wer(it["ref"], t.text))
            lats.append(t.latency_s)
            want = it.get("intent", "")
            if want and intent_of(t.text) == want:
                intent_ok += 1
        n = len(wers) or 1
        rows.append({
            "engine": eng_name,
            "n": len(wers),
            "wer_mean": round(statistics.mean(wers), 3),
            "intent_acc": round(intent_ok / n, 3),
            "lat_p50_ms": round(statistics.median(lats) * 1000, 1) if lats else 0,
            "lat_p95_ms": round(sorted(lats)[int(0.95 * (len(lats) - 1))] * 1000, 1) if lats else 0,
            "offline": getattr(engine, "offline_capable", False),
            "streaming": getattr(engine, "supports_streaming", False),
        })
        print(f"[done] {eng_name}: WER {rows[-1]['wer_mean']}, intent {rows[-1]['intent_acc']}")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    print(f"report -> {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--engines", default="google",
                    help="comma-separated engine names")
    ap.add_argument("--manifest", default="evals/stt/manifest.jsonl")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or f"evals/reports/stt_{datetime.date.today():%Y-%m-%d}.csv"
    run(a.manifest, [e.strip() for e in a.engines.split(",")], out)
