"""Tests for Phase 5.6 file intelligence (scoped workspace, dry-run, undo)."""

import sys

import pytest

sys.path.insert(0, "src")

from jarvis.perception import files as F  # noqa: E402
from jarvis.tools.registry import REGISTRY, Risk  # noqa: E402


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_WORKSPACE", str(tmp_path))
    (tmp_path / "notes.txt").write_text("hello world")
    (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8fake")
    (tmp_path / "song.mp3").write_bytes(b"ID3fake")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_text("deep")
    yield tmp_path
    F._PENDING_UNDO.clear()


def test_workspace_scoped_to_env(ws, tmp_path):
    assert F.workspace_root() == tmp_path.resolve()


def test_traversal_blocked(ws, tmp_path):
    with pytest.raises(F.ScopeError):
        F.resolve_scoped("../../etc/passwd")
    with pytest.raises(F.ScopeError):
        F.resolve_scoped("/etc/passwd")
    # inside is fine
    assert F.resolve_scoped("notes.txt").name == "notes.txt"


def test_find_files(ws):
    hits = F.find_files(name="note")
    assert len(hits) == 1 and hits[0].endswith("notes.txt")
    hits = F.find_files(ext="jpg")
    assert len(hits) == 1
    hits = F.find_files(ext=".txt")
    assert len(hits) == 2  # notes.txt + sub/deep.txt


def test_read_and_summarize(ws):
    assert "hello world" in F.read_file("notes.txt")
    summary = F.summarize_file("notes.txt")
    assert "notes.txt" in summary and "bytes" in summary


def test_move_and_inverse(ws, tmp_path):
    out = F.move_file("notes.txt", "sub/notes.txt")
    assert "moved" in out
    assert not (tmp_path / "notes.txt").exists()
    inv = F.inverse_of("move_file", {"src": "a", "dst": "b"})
    assert inv == ("move_file", {"src": "b", "dst": "a"})


def test_copy_and_inverse(ws, tmp_path):
    F.copy_file("notes.txt", "copy.txt")
    assert (tmp_path / "copy.txt").exists()
    inv = F.inverse_of("copy_file", {"src": "a", "dst": "b"})
    assert inv == ("delete_file", {"path": "b"})


def test_organize_dry_run_first(ws):
    plan = F.organize_folder(".", dry_run=True)
    assert "Plan:" in plan and "Dry run only" in plan
    # nothing moved
    assert (ws / "photo.jpg").exists()


def test_organize_execute_and_undo(ws):
    out = F.organize_folder(".", dry_run=False)
    assert "organized" in out
    assert (ws / "Images" / "photo.jpg").exists()
    assert (ws / "Audio" / "song.mp3").exists()
    pending = F.drain_pending_undo()
    assert len(pending) == 3  # top-level files only: notes, photo, song
    # every pending undo is a move back
    for tool, _args in pending:
        assert tool == "move_file"


def test_organize_never_overwrites(ws):
    (ws / "Images").mkdir()
    (ws / "Images" / "photo.jpg").write_bytes(b"existing")
    F.organize_folder(".", dry_run=False)
    assert (ws / "photo.jpg").exists()  # untouched
    assert (ws / "Images" / "photo.jpg").read_bytes() == b"existing"


def test_delete_uses_trash(ws, tmp_path):
    pytest.importorskip("send2trash")
    out = F.delete_file("notes.txt")
    assert "Recycle Bin" in out
    assert not (tmp_path / "notes.txt").exists()


def test_undo_journal_integration(ws, tmp_path):
    from jarvis.brain.loop import UndoJournal

    j = UndoJournal()
    F.move_file("notes.txt", "sub/notes.txt")
    j.record("move_file", {"src": "notes.txt", "dst": "sub/notes.txt"}, "moved")
    assert len(j) == 1

    # undo replays the inverse via executor
    def fake_executor(tool, args):
        return F.move_file(args["src"], args["dst"])

    msg = j.undo_last(fake_executor)
    assert "Wapas kar diya" in msg
    assert (tmp_path / "notes.txt").exists()


def test_bulk_undo_drained_into_journal(ws, tmp_path):
    from jarvis.brain.loop import UndoJournal

    F.organize_folder(".", dry_run=False)
    j = UndoJournal()
    j.record("organize_folder", {"path": ".", "dry_run": False}, "organized")
    assert len(j) >= 3  # per-file inverses drained

    def fake_executor(tool, args):
        assert tool == "move_file"
        return F.move_file(args["src"], args["dst"])

    while len(j):
        j.undo_last(fake_executor)
    assert (ws / "photo.jpg").exists()
    assert (ws / "notes.txt").exists()


def test_tools_registered():
    assert REGISTRY["find_files"].risk == Risk.READ
    assert REGISTRY["read_file"].risk == Risk.READ
    assert REGISTRY["read_file"].carries_external_data is True
    assert REGISTRY["move_file"].risk == Risk.REVERSIBLE
    assert REGISTRY["organize_folder"].risk == Risk.DESTRUCTIVE
    assert REGISTRY["delete_file"].risk == Risk.DESTRUCTIVE
    # no permanent-delete tool exists
    assert "permanent_delete" not in REGISTRY
    assert "delete_permanently" not in REGISTRY
