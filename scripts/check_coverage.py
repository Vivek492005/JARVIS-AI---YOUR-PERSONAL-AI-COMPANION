#!/usr/bin/env python3
"""Coverage gate for Task 8.1 (test pyramid).

Runs the unit suite under coverage and enforces:
  * every core module (policy, lane queue, memory, model router) >= 80%
  * security suite files collected (the suite itself must be 100% pass,
    which pytest already enforces by failing on any red test)

Usage:
    python scripts/check_coverage.py            # full run, enforces the gate
    python scripts/check_coverage.py --report   # just print the table

Exit code: 0 = gate passed, 1 = gate failed.
"""

from __future__ import annotations

import subprocess
import sys

CORE_MODULES = [
    "src/jarvis/policy/__init__.py",
    "src/jarvis/policy/audit.py",
    "src/jarvis/policy/command_policy.py",
    "src/jarvis/core/lanes.py",
    "src/jarvis/brain/memory/",
    "src/jarvis/brain/model_router.py",
]
CORE_MIN_COVERAGE = 80.0

# Files with failures that pre-date Phase 8 (verified identical on the pristine
# v0.9.0 tree via a worktree; the team decided not to chase them). They are
# excluded from the gate run, NOT hidden: pytest still reports them as failed
# in the normal suite run.
KNOWN_BROKEN = [
    "tests/unit/test_providers.py",  # 5x ModuleNotFoundError
    "tests/integration/test_observability.py::test_doctor_packages_source_checkout_warns_not_fails",
    "tests/integration/test_privacy.py::test_egress_toggle_blocks_client_creation",
    "tests/integration/test_main.py",  # legacy GUI collection error
]


def _run(cmd: list[str]) -> int:
    print("+", " ".join(cmd), flush=True)
    # S603: argv is fully constructed here (fixed strings + module constants),
    # never from user/LLM input. This is a dev-only gate script.
    return subprocess.run(cmd).returncode  # noqa: S603


def main() -> int:
    report_only = "--report" in sys.argv
    deselect_args: list[str] = ["--ignore", "tests/integration/test_main.py"]
    for item in KNOWN_BROKEN[1:]:  # [0] is test_providers.py, handled below
        deselect_args += ["--deselect", item]
    rc = _run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "-m",
            "pytest",
            "tests/",
            "-m",
            "not hardware and not live",
            "-q",
            "--ignore",
            KNOWN_BROKEN[0],
            *deselect_args,
        ]
    )
    if rc != 0:
        print("coverage run: test suite itself failed -> gate FAILED")
        return 1
    rc = _run([sys.executable, "-m", "coverage", "report", "--include=" + ",".join(CORE_MODULES)])
    if rc != 0:
        return 1
    if report_only:
        return 0
    # Parse per-file numbers from a second machine-readable pass.
    out = subprocess.run(  # noqa: S603  (fixed argv, dev-only script)
        [
            sys.executable,
            "-m",
            "coverage",
            "report",
            "--include=" + ",".join(CORE_MODULES),
            "--format=text",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    failures: list[str] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0].startswith("src/jarvis/"):
            try:
                pct = float(parts[-1].rstrip("%"))
            except ValueError:
                continue
            if pct < CORE_MIN_COVERAGE:
                failures.append(f"{parts[0]}: {pct:.1f}% < {CORE_MIN_COVERAGE}%")
    if failures:
        print("COVERAGE GATE FAILED:")
        print("\n".join(failures))
        return 1
    print(f"COVERAGE GATE PASSED: all core modules >= {CORE_MIN_COVERAGE}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
