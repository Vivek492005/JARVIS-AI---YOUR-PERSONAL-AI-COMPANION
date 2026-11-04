"""Tests for Phase 5.9 postconditions (honest verify, verifiable flag)."""

import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, "tests")

from jarvis.perception import postconditions as PC  # noqa: E402
from fakes.fake_desktop import install_fake_desktop, uninstall_fake_desktop  # noqa: E402
from jarvis.perception.backends import ElementNode  # noqa: E402


@pytest.fixture()
def desktop():
    made = install_fake_desktop()
    uia = made["uia"]
    uia.add_window(
        "App",
        "app.exe",
        children=[
            ElementNode(element_id="e0", role="textbox", name="Name", bounds=(10, 10, 80, 24)),
        ],
    )
    yield made
    uninstall_fake_desktop()


def test_unverifiable_tools_flagged():
    assert not PC.is_verifiable("open_website")
    assert not PC.is_verifiable("web_search")
    assert PC.is_verifiable("uia_invoke")
    assert PC.is_verifiable("move_file")


def test_honest_message_unverifiable():
    msg = PC.honest_message("open_website", {}, "Opening youtube.")
    assert "Bhej diya, confirm nahi kar paaya" in msg
    assert "Ho gaya" not in msg


def test_honest_message_verified():
    msg = PC.honest_message("uia_invoke", {}, "invoked")
    assert msg.startswith("Ho gaya")


def test_honest_message_failed():
    msg = PC.honest_message("uia_invoke", {}, "invoke failed: unknown element zz")
    assert "Nahi hua" in msg


def test_uia_set_text_readback(desktop):
    (made,) = (desktop,)  # noqa
    uia = made["uia"]
    # handler-level: set then verify via read-back
    from jarvis.perception.uia import UIAController

    ctl = UIAController(backend=uia)
    assert ctl.set_text("e0", "hello") == "text set"
    ok, evidence = PC.verify("uia_set_text", {"element_id": "e0", "value": "hello"}, "text set")
    assert ok and "read-back matches" in evidence


def test_uia_set_text_readback_mismatch(desktop):
    made = desktop
    uia = made["uia"]
    uia.text_set["e0"] = "something else"  # backend disagrees
    ok, evidence = PC.verify("uia_set_text", {"element_id": "e0", "value": "hello"}, "text set")
    assert not ok and "mismatch" in evidence


def test_move_file_disk_verified(desktop, tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_WORKSPACE", str(tmp_path))
    from jarvis.perception import files as F

    (tmp_path / "a.txt").write_text("x")
    F.move_file("a.txt", "b.txt")
    ok, evidence = PC.verify("move_file", {"src": "a.txt", "dst": "b.txt"}, "moved a.txt -> b.txt")
    assert ok and "verified on disk" in evidence


def test_move_file_disk_wrong(desktop, tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_WORKSPACE", str(tmp_path))
    ok, evidence = PC.verify(
        "move_file", {"src": "nope.txt", "dst": "b.txt"}, "moved nope.txt -> b.txt"
    )
    assert not ok


def test_vlm_click_handoff_not_ok():
    ok, evidence = PC.verify("vlm_click", {"prompt": "login"}, "Mujhse nahi hoga, aap kar do.")
    assert not ok and "handed off" in evidence


def test_vlm_click_unverified_honest():
    ok, evidence = PC.verify(
        "vlm_click", {"prompt": "save"}, "clicked 'Save' (mark 1; unverified — no postcondition)"
    )
    assert ok and "unverified" in evidence


def test_browser_submit_handoff():
    ok, _ = PC.verify("browser_submit", {}, "Mujhse nahi hoga, aap kar do.")
    assert not ok


def test_verifier_delegates_to_perception(desktop):
    from jarvis.brain.loop import Verifier

    v = Verifier()
    ok, evidence = v.verify("uia_invoke", {}, "invoked")
    assert ok
    # legacy tools still work through the old path
    ok, _ = v.verify("manage_notes", {"action": "save", "content": "x"}, "saved note")
    assert ok


def test_unknown_tool_honest_pass():
    ok, evidence = PC.verify("mystery_tool", {}, "did a thing")
    assert ok and "no postcondition" in evidence
