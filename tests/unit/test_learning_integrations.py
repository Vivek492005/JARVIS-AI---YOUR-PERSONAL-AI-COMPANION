"""Integration tests: learned rules feed the reflex matcher, learned
snippets feed the prompt, and the undo hook feeds the learning store."""

import json
import sys

sys.path.insert(0, "src")

from jarvis.brain.prompts.builder import PromptBuilder, _read_learned_layer
from jarvis.brain.reflex import ReflexMatcher, _load_learned_rules


def test_learned_rules_file_empty_by_default():
    assert _load_learned_rules() == []


def test_learned_rules_merge_after_builtins(tmp_path, monkeypatch):
    import jarvis.brain.reflex as reflex_mod

    p = tmp_path / "reflex_learned.json"
    p.write_text(
        json.dumps(
            [
                {
                    "id": "learned_demo",
                    "patterns": ["^demo please$"],
                    "tool": "get_time",
                    "args": {},
                    "reply": "",
                    "compute": None,
                }
            ]
        ),
        encoding="utf-8",
    )
    orig = reflex_mod._load_learned_rules
    monkeypatch.setattr(reflex_mod, "_load_learned_rules", lambda path=None: orig(path or p))
    m = ReflexMatcher()
    ids = [r.get("id") for r in m._rules]
    assert "learned_demo" in ids
    # Built-ins still come first (they win ties).
    assert ids.index("learned_demo") > 0


def test_load_learned_rules_skips_malformed(tmp_path):
    p = tmp_path / "reflex_learned.json"
    p.write_text(
        json.dumps(
            [
                {"id": "bad1", "tool": "x"},  # no patterns
                {"id": "bad2", "patterns": "not-a-list", "tool": "x"},
                {"id": "good", "patterns": ["^ok$"], "tool": "get_time"},
                "not-a-dict",
            ]
        ),
        encoding="utf-8",
    )
    out = _load_learned_rules(path=p)
    assert [r["id"] for r in out] == ["good"]


def test_load_learned_rules_missing_file(tmp_path):
    assert _load_learned_rules(path=tmp_path / "nope.json") == []


def test_learned_prompt_layer_empty_by_default():
    # The shipped learned.md is comment-only -> no layer injected.
    assert _read_learned_layer() == ""


def test_learned_prompt_layer_included_in_build(tmp_path, monkeypatch):
    import jarvis.brain.prompts.builder as bmod

    p = tmp_path / "learned.md"
    p.write_text("## Learned: x\n\nBe careful.\n", encoding="utf-8")
    monkeypatch.setattr(bmod, "_read_learned_layer", lambda: p.read_text(encoding="utf-8").strip())
    built = PromptBuilder(workspace=None).build()
    assert "## Learned: x" in built


def test_undo_hook_records_correction(tmp_path, monkeypatch):
    import jarvis.learning.recorder as recmod

    monkeypatch.setattr(recmod, "_recorder", None)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from jarvis.brain.loop import UndoJournal

    uj = UndoJournal()
    uj._stack.append(("set_volume", {"level": 5}, "set_volume (orig)"))
    msg = uj.undo_last(lambda t, a: "undone")
    assert "Wapas kar diya" in msg
    assert recmod._recorder.store.count_corrections() == 1
