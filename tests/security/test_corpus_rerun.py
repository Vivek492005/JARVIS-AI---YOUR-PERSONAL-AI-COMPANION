"""Task 1.11: the injection corpus also runs inside the security suite.

The corpus itself lives in evals/cases/injection.jsonl; the runner is
shared with tests/test_injection_corpus.py so both stay in sync.
"""

import sys

sys.path.insert(0, "tests")

from test_injection_corpus import _cases, _run  # noqa: E402


def test_security_injection_corpus():
    failures = [c["id"] for c in _cases() if not _run(c)]
    assert not failures, f"injection cases failed: {failures}"
