"""Shared test fixtures for the JARVIS suite (Master Plan Task 2.8).

Import-time stubs for Windows-only / heavy modules, so every test module
stays headless without repeating the boilerplate. Modules that need the
*real* implementation (e.g. the reflex tests need the real fuzzywuzzy
scorer) restore it with the ``real_fuzzywuzzy`` fixture.
"""

import sys
from unittest.mock import MagicMock

# Stub display/Windows-only modules so tests run headless on any OS.
for _mod in ("pyautogui",):
    sys.modules.setdefault(_mod, MagicMock(name=_mod))

import pytest  # noqa: E402


@pytest.fixture
def real_fuzzywuzzy():
    """Restore the real ``fuzzywuzzy`` scorer.

    Several test modules install a MagicMock for ``fuzzywuzzy`` (whole
    package or just the ``fuzz`` attribute) for dependency isolation, and
    some import ``voice.interface`` while the mock is in place — binding
    the mock at import time. Request this fixture in tests that need the
    real scorer.
    """
    import importlib
    import types

    real_fuzz = None
    try:
        if not isinstance(sys.modules.get("fuzzywuzzy"), types.ModuleType):
            # Whole-package mock: evict it so the real package imports.
            sys.modules.pop("fuzzywuzzy", None)
            sys.modules.pop("fuzzywuzzy.fuzz", None)
        real_fuzz = importlib.import_module("fuzzywuzzy.fuzz")
        pkg = sys.modules.get("fuzzywuzzy")
        if isinstance(pkg, types.ModuleType) and isinstance(getattr(pkg, "fuzz", None), MagicMock):
            pkg.fuzz = real_fuzz
    except ImportError:
        pass

    if real_fuzz is not None:
        # Rebind module globals that captured the mock at import time.
        for modname in ("jarvis.voice.interface",):
            mod = sys.modules.get(modname)
            if mod is not None and isinstance(getattr(mod, "fuzz", None), MagicMock):
                mod.fuzz = real_fuzz
    yield
