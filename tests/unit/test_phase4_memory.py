"""Tests for Phase 4.4 (memory system)."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("pyautogui", MagicMock(name="pyautogui"))

import pytest

from jarvis.brain.memory.commands import MemoryCommands, parse
from jarvis.brain.memory.consolidate import Consolidator
from jarvis.brain.memory.decay import decay
from jarvis.brain.memory.profile import ProfileStore
from jarvis.brain.memory.retrieval import Retriever, jaccard_similarity
from jarvis.brain.memory.store import MemoryStore
from jarvis.brain.memory.write_policy import (
    WriteRequest,
    contains_sensitive,
    guard_write_source,
    validate_write,
)


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path / "m.db")
    yield s
    s.close()


class TestStore:
    def test_fact_roundtrip(self, store):
        fid = store.add_fact("browser", "Chrome", source="user")
        facts = store.all_facts()
        assert len(facts) == 1 and facts[0].value == "Chrome"

    def test_bad_source_rejected(self, store):
        with pytest.raises(ValueError):
            store.add_fact("k", "v", source="web")

    def test_delete_like(self, store):
        store.add_fact("car", "red", source="user")
        store.add_fact("bike", "blue", source="user")
        assert store.delete_facts_like("car") == 1
        assert len(store.all_facts()) == 1

    def test_episodes(self, store):
        store.add_episode("user", "hello", session="s1", tool="", outcome="")
        assert len(store.recent_episodes()) == 1


class TestWritePolicy:
    def test_sensitive_blocked(self):
        assert contains_sensitive("my password: hunter2") is not None
        assert contains_sensitive("card 4111 1111 1111 1111") is not None
        assert contains_sensitive("my browser is Chrome") is None

    def test_web_source_rejected(self):
        with pytest.raises(ValueError):
            guard_write_source("web")
        with pytest.raises(ValueError):
            guard_write_source("file")

    def test_validate_write(self):
        assert validate_write(WriteRequest("k", "v", "user")) is None
        assert validate_write(WriteRequest("k", "v", "web")) is not None
        assert validate_write(WriteRequest("k", "my password: x", "user")) is not None
        assert validate_write(WriteRequest("", "v", "user")) is not None


class TestRetrieval:
    def test_similarity_ranking(self, store):
        store.add_fact("default browser", "Chrome", source="user")
        store.add_fact("favorite food", "biryani", source="user")
        r = Retriever(store).retrieve("which browser do I use?")
        assert r and r[0].fact.value == "Chrome"

    def test_jaccard(self):
        assert jaccard_similarity("a b c", "a b c") == 1.0
        assert jaccard_similarity("a b", "c d") == 0.0


class TestCommands:
    def test_remember_and_forget(self, store):
        mc = MemoryCommands(store)
        out = mc.handle(parse("yaad rakhna meri car red hai"))
        assert "Yaad rakh liya" in out
        out = mc.handle(parse("bhool ja car"))
        assert out.startswith("Bhool gaya")

    def test_list_empty(self, store):
        mc = MemoryCommands(store)
        assert "kuch khaas" in mc.handle(parse("tumhe kya yaad hai?"))

    def test_wipe_needs_confirm(self, store):
        mc = MemoryCommands(store)
        out = mc.handle(parse("memory delete all"))
        assert out.startswith("CONFIRM_WIPE")
        assert len(store.all_facts()) == 0  # nothing wiped yet
        mc.confirm_wipe()  # explicit

    def test_parse_none(self):
        assert parse("chrome khol do").kind == "none"


class TestProfile:
    def test_append_approved(self, tmp_path):
        ps = ProfileStore(tmp_path)
        ps.append_approved(["likes lofi music"])
        assert "lofi" in ps.read()
        assert "pending approval" in ps.propose_lines(["x"])[0]


class TestConsolidateDecay:
    def test_consolidate_proposals(self, store):
        store.add_episode("user", "chrome kholo")
        store.add_episode("user", "notepad kholo")
        props = Consolidator(store).run()
        assert isinstance(props, list)

    def test_decay_and_purge(self, store):
        store.add_fact("old", "thing", source="user", importance=0.9,
                       expires="2000-01-01T00:00:00")
        assert store.purge_expired() == 1
        store.add_fact("k", "v", source="user", importance=0.9)
        decay(store)  # must not crash; fresh fact barely decays
        assert store.all_facts()[0].importance <= 0.9
