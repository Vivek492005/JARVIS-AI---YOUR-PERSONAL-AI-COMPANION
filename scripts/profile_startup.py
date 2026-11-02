#!/usr/bin/env python3
"""Profile any `jarvis` CLI invocation with cProfile (Task 8.2).

Usage:
    python scripts/profile_startup.py --help
    python scripts/profile_startup.py doctor --latency

Prints the top 30 cumulative-time functions. Use before v1.0.0 to catch
import-time regressions (heavy deps must stay lazily imported).
"""
from __future__ import annotations

import cProfile
import io
import os
import pstats
import runpy
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    argv = sys.argv[1:] or ["--help"]
    sys.path.insert(0, os.path.join(REPO, "src"))
    sys.argv = ["jarvis", *argv]
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        runpy.run_module("jarvis.cli", run_name="__main__")
    except SystemExit:
        pass
    profiler.disable()
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
    stats.print_stats(30)
    print(stream.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
