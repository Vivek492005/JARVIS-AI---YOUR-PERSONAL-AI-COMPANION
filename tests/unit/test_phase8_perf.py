"""Performance-budget gate tests (Task 8.2).

Marked `perf`: timing-sensitive, but the bounds are generous (CI-safe).
The Master Plan's stricter targets live in docs/PERF_BUDGET.md with measured
values.
"""

import os
import subprocess
import sys
import time

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.perf


def test_cli_cold_start_within_budget():
    """`jarvis --help` must start in < 10 s (plan target: < 3 s; measured ~0.3 s)."""
    env = dict(os.environ, PYTHONPATH=os.path.join(REPO, "src"))
    start = time.time()
    proc = subprocess.run(  # noqa: S603  (fixed argv, dev-only test)
        [sys.executable, "-m", "jarvis", "--help"],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO,
    )
    elapsed = time.time() - start
    assert proc.returncode == 0, proc.stderr[-500:]
    assert elapsed < 10.0, f"CLI cold start took {elapsed:.1f}s (> 10s gate)"


def test_reflex_match_within_budget():
    """A reflex match must complete in < 0.5 s (measured: milliseconds)."""
    from jarvis.brain.reflex import ReflexMatcher

    matcher = ReflexMatcher()
    start = time.time()
    hit = matcher.match("volume up")
    elapsed = time.time() - start
    assert elapsed < 0.5, f"reflex match took {elapsed:.3f}s (> 0.5s gate)"
    assert hit is not None  # sanity: the rule data actually loaded
