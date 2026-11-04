"""Tests for scripts/check_coverage.py (Task 8.1 gate plumbing)."""

import importlib.util
import os

# tests/unit/<this file> -> repo root
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_script():
    path = os.path.join(REPO, "scripts", "check_coverage.py")
    spec = importlib.util.spec_from_file_location("check_coverage", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_core_modules_exist():
    mod = _load_script()
    for entry in mod.CORE_MODULES:
        full = os.path.join(REPO, entry)
        assert os.path.exists(full), f"coverage target missing: {entry}"


def test_known_broken_entries_are_real():
    """The exclusion list must reference real files/tests, never hide silently."""
    mod = _load_script()
    assert mod.KNOWN_BROKEN, "exclusion list must not be empty"
    for entry in mod.KNOWN_BROKEN:
        file_part = entry.split("::")[0]
        assert os.path.exists(os.path.join(REPO, file_part)), entry


def test_gate_threshold_matches_plan():
    mod = _load_script()
    assert mod.CORE_MIN_COVERAGE == 80.0
