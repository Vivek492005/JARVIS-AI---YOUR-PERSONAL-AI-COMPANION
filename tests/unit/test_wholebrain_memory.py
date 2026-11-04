"""Tests for the whole-brain Supermemory integration (Phases A-D).

Covers: provider interface, SupermemoryProvider (mocked HTTP), HybridProvider
fail-open fallback, capture heuristics, and command routing through providers.
"""

import json
import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("pyautogui", MagicMock(name="pyautogui"))

import pytest  # noqa: E402

from jarvis.brain.memory.capture import extract_candidates  # noqa: E402
from jarvis.brain.memory.commands import MemoryCommands, parse  # noqa: E402
from jarvis.brain.memory.hybrid import HybridProvider  # noqa: E402
from jarvis.brain.memory.provider import Memory, MemoryProvider, Profile  # noqa: E402
from jarvis.brain.memory.sqlite_provider import SQLiteProvider  # noqa: E402
from jarvis.brain.memory.store import MemoryStore  # noqa: E402
from jarvis.brain.memory.supermemory_provider import (  # noqa: E402
    SupermemoryError,
    SupermemoryProvider,
)


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def sqlite(tmp_db):
    p = SQLiteProvider(tmp_db)
    yield p
    p.close()


@pytest.fixture
def hybrid(tmp_db):
    # Point semantic at a dead port so every test exercises fail-open.
    sem = SupermemoryProvider(base_url="http://127.0.0.1:1", timeout=0.5)
    h = HybridProvider(sqlite_path=tmp_db, supermemory=sem)
    yield h
    h.close()


# -- provider interface -------------------------------------------------


class TestProviderInterface:
    def test_sqlite_implements_interface(self, sqlite):
        assert isinstance(sqlite, MemoryProvider)

    def test_supermemory_implements_interface(self):
        assert isinstance(SupermemoryProvider(), MemoryProvider)

    def test_hybrid_implements_interface(self, hybrid):
        assert isinstance(hybrid, MemoryProvider)


# -- SQLiteProvider ------------------------------------------------------


class TestSQLiteProvider:
    def test_add_search_roundtrip(self, sqlite):
        mid = sqlite.add("my favorite color is blue", {"source": "user"})
        assert mid
        res = sqlite.search("favorite color", 5)
        assert any("blue" in m.text for m in res)

    def test_add_blocks_sensitive(self, sqlite):
        with pytest.raises(ValueError):
            sqlite.add("my password: hunter2", {"source": "user"})

    def test_forget(self, sqlite):
        sqlite.add("my car is red", {"source": "user"})
        assert sqlite.forget("car") >= 1
        assert not any("red" in m.text for m in sqlite.search("car", 5))

    def test_profile(self, sqlite):
        sqlite.add("my editor is vscode", {"source": "user"})
        prof = sqlite.profile()
        assert isinstance(prof, Profile)
        assert any("vscode" in f for f in prof.facts)

    def test_health(self, sqlite):
        assert sqlite.health() is True

    def test_export_wipe(self, sqlite):
        sqlite.add("my pet is a cat", {"source": "user"})
        assert "cat" in sqlite.export()
        sqlite.wipe()
        assert sqlite.profile().facts == []


# -- SupermemoryProvider (mocked HTTP) ------------------------------------


def _fake_response(payload):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


class TestSupermemoryProvider:
    def _prov(self):
        return SupermemoryProvider(base_url="http://127.0.0.1:6767", timeout=1)

    def test_add_posts_document(self):
        prov = self._prov()
        with patch("urllib.request.urlopen", return_value=_fake_response({"id": "doc1"})):
            mid = prov.add("hello world", {"source": "user"})
        assert mid == "doc1"

    def test_add_blocks_sensitive(self):
        prov = self._prov()
        with pytest.raises(ValueError):
            prov.add("my password: hunter2")

    def test_search_parses_results(self):
        prov = self._prov()
        payload = {
            "results": [
                {"id": "m1", "content": "User likes cricket", "score": 0.9},
                {"memory": {"id": "m2", "content": "User dislikes rain"}, "score": 0.4},
            ]
        }
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
            res = prov.search("sports", 5)
        assert len(res) == 2
        assert res[0].text == "User likes cricket"
        assert res[0].score == 0.9
        assert all(isinstance(m, Memory) for m in res)

    def test_search_empty_query(self):
        prov = self._prov()
        assert prov.search("", 5) == []
        assert prov.search("   ", 5) == []

    def test_forget_dryrun_then_real(self):
        prov = self._prov()
        calls = []

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode())
            calls.append(body)
            if body.get("dryRun"):
                return _fake_response({"memories": [{"id": "a"}, {"id": "b"}]})
            return _fake_response({"ok": True})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            n = prov.forget("old project")
        assert n == 2
        assert calls[0]["dryRun"] is True
        assert calls[1]["dryRun"] is False

    def test_profile(self):
        prov = self._prov()
        payload = {"profile": {"summary": "Test user", "facts": ["likes chai"]}}
        with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
            prof = prov.profile()
        assert prof.summary == "Test user"
        assert prof.facts == ["likes chai"]

    def test_health_false_on_connection_refused(self):
        import urllib.error

        prov = self._prov()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("refused"),
        ):
            assert prov.health() is False

    def test_unreachable_raises_supermemory_error(self):
        import urllib.error

        prov = self._prov()
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("refused"),
        ):
            with pytest.raises(SupermemoryError):
                prov.search("x", 1)

    def test_wipe_raises(self):
        prov = self._prov()
        with pytest.raises(SupermemoryError):
            prov.wipe()


# -- HybridProvider fail-open ----------------------------------------------


class TestHybridFailOpen:
    def test_search_falls_back_to_sqlite(self, hybrid):
        hybrid.add("my favorite food is biryani", {"source": "user"})
        res = hybrid.search("favorite food", 5)
        assert any("biryani" in m.text for m in res)
        assert hybrid.backend_used() == "sqlite"

    def test_add_mirrors_to_sqlite(self, hybrid):
        hybrid.add("my city is Dehradun", {"source": "user"})
        # Even though semantic failed, the sqlite mirror has it.
        assert any("Dehradun" in m.text for m in hybrid.sqlite.search("city", 5))

    def test_forget_both_backends(self, hybrid):
        hybrid.add("my bike is red", {"source": "user"})
        assert hybrid.forget("bike") >= 1
        assert not any("red" in m.text for m in hybrid.search("bike", 5))

    def test_health_true_when_semantic_down(self, hybrid):
        assert hybrid.health() is True

    def test_semantic_available_false(self, hybrid):
        assert hybrid.semantic_available() is False

    def test_kill_switch(self, hybrid):
        hybrid.set_semantic_enabled(False)
        hybrid.add("kill switch test memory", {"source": "user"})
        assert hybrid.backend_used() == "sqlite"
        hybrid.set_semantic_enabled(True)

    def test_semantic_success_path(self, tmp_db):
        sem = SupermemoryProvider(base_url="http://127.0.0.1:6767", timeout=1)
        h = HybridProvider(sqlite_path=tmp_db, supermemory=sem)
        try:
            with patch("urllib.request.urlopen", return_value=_fake_response({"id": "d9"})):
                mid = h.add("semantic path check", {"source": "user"})
            assert mid == "d9"
            assert h.backend_used() == "supermemory"
        finally:
            h.close()


# -- capture heuristics -----------------------------------------------------


class TestCapture:
    def test_name(self):
        c = extract_candidates("my name is Vivek")
        assert any("Vivek" in x.text for x in c)

    def test_preference(self):
        c = extract_candidates("I really like strong chai")
        assert any("chai" in x.text for x in c)

    def test_my_x_is_y(self):
        c = extract_candidates("my default browser is Chrome")
        assert any("Chrome" in x.text for x in c)

    def test_hindi(self):
        c = extract_candidates("mujhe cricket pasand hai")
        assert any("cricket" in x.text for x in c)

    def test_correction(self):
        c = extract_candidates("no, I meant the blue one")
        assert any("blue" in x.text for x in c)

    def test_too_short(self):
        assert extract_candidates("hi") == []

    def test_no_match(self):
        assert extract_candidates("what is the weather like today") == []

    def test_max_candidates(self):
        c = extract_candidates(
            "my name is Vivek. I like chai. my city is Dehradun. "
            "my editor is vscode. I love cricket.",
            max_candidates=2,
        )
        assert len(c) <= 2

    def test_never_raises(self):
        assert extract_candidates(None) == []
        assert extract_candidates("") == []


# -- command routing through providers ---------------------------------------


class TestCommandRouting:
    def test_remember_forget_list_via_hybrid(self, hybrid):
        mc = MemoryCommands(hybrid)
        out = mc.handle(parse("yaad rakhna meri bike red hai"))
        assert "Yaad rakh liya" in out
        out = mc.handle(parse("tumhe kya yaad hai?"))
        assert "bike" in out
        out = mc.handle(parse("bhool ja bike"))
        assert "Bhool gaya" in out

    def test_remember_blocks_sensitive(self, hybrid):
        mc = MemoryCommands(hybrid)
        out = mc.handle(parse("yaad rakhna my password: hunter2"))
        assert "Yaad nahi rakh paya" in out

    def test_legacy_store_still_works(self, tmp_db):
        mc = MemoryCommands(MemoryStore(tmp_db))
        out = mc.handle(parse("remember my editor is vscode"))
        assert "Yaad rakh liya" in out
        out = mc.handle(parse("what do you remember?"))
        assert "vscode" in out

    def test_hindi_regexes(self):
        assert parse("yaad rakhna meri car red hai").kind == "remember"
        assert parse("bhool ja car").kind == "forget"
        assert parse("tumhe kya yaad hai").kind == "list"
        assert parse("memory export").kind == "export"
        assert parse("memory delete all").kind == "wipe"
        assert parse("hello there").kind == "none"

    def test_export(self, hybrid):
        mc = MemoryCommands(hybrid)
        mc.handle(parse("yaad rakhna meri car red hai"))
        out = mc.handle(parse("memory export"))
        assert "MEMORY EXPORT" in out

    def test_wipe_flow(self, hybrid):
        mc = MemoryCommands(hybrid)
        mc.handle(parse("yaad rakhna meri car red hai"))
        out = mc.handle(parse("memory delete all"))
        assert out.startswith("CONFIRM_WIPE:")
        out = mc.confirm_wipe()
        assert "delete kar di" in out
