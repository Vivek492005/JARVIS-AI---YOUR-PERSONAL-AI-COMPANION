"""Tests for Task 3.10: latency budget + instrumentation."""

from __future__ import annotations

import csv
import os
import sys
import time

sys.path.insert(0, "src")

from jarvis.voice.latency import (  # noqa: E402
    BUDGET_MS,
    StageTimer,
    format_latency_report,
    latency_summary,
)


def test_budget_table_matches_plan():
    assert BUDGET_MS["vad_endpoint"] == 300.0
    assert BUDGET_MS["stt_final"] == 250.0
    assert BUDGET_MS["llm_first_token"] == 400.0
    assert BUDGET_MS["tts_first_audio"] == 250.0
    assert BUDGET_MS["total"] == 1500.0
    assert BUDGET_MS["reflex"] == 200.0


def test_stage_timer_measures():
    t = StageTimer()
    with t.time("reflex"):
        time.sleep(0.01)
    assert t.timings["reflex"] >= 10.0
    assert t.over_budget() == {}  # 10 ms < 200 ms budget


def test_over_budget_detected():
    t = StageTimer()
    t.timings["stt_final"] = 900.0
    over = t.over_budget()
    assert over == {"stt_final": 650.0}


def test_latency_summary_from_csv(tmp_path):
    d = str(tmp_path)
    with open(os.path.join(d, "2026-11-01.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["total_ms", "reflex_match_ms", "stt_final_ms"])
        w.writeheader()
        for total in (1000, 1200, 2000):
            w.writerow({"total_ms": total, "reflex_match_ms": 50, "stt_final_ms": 100})
    reports = {r.stage: r for r in latency_summary(d)}
    assert reports["total"].p50_ms == 1200.0
    assert reports["total"].status == "ok"      # <= 1500
    assert reports["reflex"].p50_ms == 50.0
    assert reports["vad_endpoint"].status == "nodata"
    assert reports["vad_endpoint"].n == 0


def test_latency_summary_over_budget(tmp_path):
    d = str(tmp_path)
    with open(os.path.join(d, "2026-11-01.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["total_ms"])
        w.writeheader()
        for _ in range(3):
            w.writerow({"total_ms": 3000})
    reports = {r.stage: r for r in latency_summary(d)}
    assert reports["total"].status == "over"


def test_format_report(tmp_path):
    d = str(tmp_path)
    out = format_latency_report(latency_summary(d))
    assert "no data" in out and "budget" in out


def test_doctor_latency_flag(capsys):
    import argparse
    sys.path.insert(0, "src")
    from jarvis.cli import build_parser, _cmd_doctor
    args = build_parser().parse_args(["doctor", "--latency"])
    assert args.latency is True
    rc = _cmd_doctor(args)
    assert rc == 0
    captured = capsys.readouterr()
    assert "latency budget" in captured.out
