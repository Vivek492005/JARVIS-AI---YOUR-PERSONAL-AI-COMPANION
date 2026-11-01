# tests/live/ — real-API tests (Master Plan Task 2.8)

Opt-in only. These hit real provider APIs and cost money / need keys,
so they never run in CI and are deselected by default:

    pytest -m "not hardware and not live"   # default, no live tests
    JARVIS_LIVE_TESTS=1 pytest tests/live -m live   # explicit opt-in

Every test in this directory must carry the `live` marker:

    import os, pytest
    pytestmark = [pytest.mark.live,
                  pytest.mark.skipif(not os.getenv("JARVIS_LIVE_TESTS"),
                                     reason="opt-in: set JARVIS_LIVE_TESTS=1")]
