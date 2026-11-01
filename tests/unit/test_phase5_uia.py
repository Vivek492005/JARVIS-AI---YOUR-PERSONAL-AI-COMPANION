"""Tests for Phase 5.2 UI Automation layer."""

import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, "tests")

from jarvis.perception import backends as B  # noqa: E402
from jarvis.perception.backends import ElementNode  # noqa: E402
from jarvis.perception.privacy import SensitiveWindowError  # noqa: E402
from jarvis.perception.uia import (  # noqa: E402
    DESTRUCTIVE_LABELS,
    UIAController,
    controller,
    invoke_risk_for_label,
)
from jarvis.tools.registry import REGISTRY, Risk, resolve  # noqa: E402
from fakes.fake_desktop import install_fake_desktop, uninstall_fake_desktop  # noqa: E402


@pytest.fixture()
def desktop():
    made = install_fake_desktop()
    uia = made["uia"]
    handle = uia.add_window("Untitled - Notepad", "notepad.exe", children=[
        ElementNode(element_id="e0", role="menu", name="File"),
        ElementNode(element_id="e1", role="button", name="Save"),
        ElementNode(element_id="e2", role="button", name="Delete all"),
    ])
    # Re-index children added via constructor
    uia._index(uia.trees[handle])
    yield made, uia, handle
    uninstall_fake_desktop()


def test_describe_screen_compact_tree(desktop):
    made, uia, handle = desktop
    ctl = UIAController(backend=uia)
    out = ctl.describe_screen(handle=handle, depth=2)
    assert "Untitled - Notepad" in out
    assert "[button] 'Save'" in out
    assert "#e1" in out


def test_describe_screen_refuses_sensitive(desktop):
    made, uia, handle = desktop
    uia.add_window("KeePassXC", "keepassxc.exe")
    ctl = UIAController(backend=uia)
    # active window via FakeContext is Notepad; pass the sensitive handle
    sens = [h for h, w in uia.windows.items() if "keepass" in w.title.lower()][0]
    with pytest.raises(SensitiveWindowError):
        ctl.describe_screen(handle=sens)


def test_find_uses_cache(desktop):
    made, uia, handle = desktop
    ctl = UIAController(backend=uia)
    el1 = ctl.find(name="Save", role="button", handle=handle)
    el2 = ctl.find(name="Save", role="button", handle=handle)
    assert el1 is el2
    assert el1.element_id == "e1"


def test_find_miss_returns_none(desktop):
    made, uia, handle = desktop
    ctl = UIAController(backend=uia)
    assert ctl.find(name="Nope", handle=handle) is None


def test_invoke_and_set_text(desktop):
    made, uia, handle = desktop
    ctl = UIAController(backend=uia)
    assert ctl.invoke("e1") == "invoked"
    assert "e1" in uia.invoked
    assert ctl.set_text("e1", "hello") == "text set"
    assert uia.text_set["e1"] == "hello"
    assert "unknown element" in ctl.invoke("zz9")


def test_invoke_risk_labels():
    assert invoke_risk_for_label("Delete all") == Risk.DESTRUCTIVE
    assert invoke_risk_for_label("Send") == Risk.DESTRUCTIVE
    assert invoke_risk_for_label("Pay now") == Risk.DESTRUCTIVE
    assert invoke_risk_for_label("Install") == Risk.DESTRUCTIVE
    assert invoke_risk_for_label("Save") == Risk.REVERSIBLE
    assert invoke_risk_for_label("Cancel") == Risk.REVERSIBLE


def test_resolve_uia_invoke_escalates(desktop):
    made, uia, handle = desktop
    # e2 = "Delete all" -> destructive
    spec = resolve("uia_invoke", {"element_id": "e2"})
    assert spec is not None and spec.name == "uia_invoke.destructive"
    assert spec.risk == Risk.DESTRUCTIVE
    # e1 = "Save" -> reversible
    spec = resolve("uia_invoke", {"element_id": "e1"})
    assert spec is not None and spec.name == "uia_invoke.normal"
    assert spec.risk == Risk.REVERSIBLE


def test_resolve_uia_invoke_fails_closed_unknown_element(desktop):
    made, uia, handle = desktop
    spec = resolve("uia_invoke", {"element_id": "zz-nope"})
    assert spec is not None and spec.risk == Risk.DESTRUCTIVE


def test_resolve_uia_invoke_fails_closed_no_backend():
    B.clear_backends()
    try:
        spec = resolve("uia_invoke", {"element_id": "e1"})
        assert spec is not None and spec.risk == Risk.DESTRUCTIVE
    finally:
        pass  # other tests reinstall fakes via fixture


def test_tools_registered():
    for name in ("describe_screen", "uia_find", "uia_invoke",
                 "uia_get_text", "uia_set_text"):
        assert name in REGISTRY, name
    assert REGISTRY["describe_screen"].risk == Risk.READ
    assert REGISTRY["describe_screen"].carries_external_data is True
    assert REGISTRY["uia_get_text"].carries_external_data is True


def test_run_action_gates_uia(desktop):
    from jarvis.tools.actions import run_action
    made, uia, handle = desktop
    # describe_screen via the real gate (FakeContext active window = Notepad)
    verdict, result = run_action("describe_screen", {})
    assert verdict == "allow", result
    assert "Notepad" in result


def test_run_action_uia_invoke_destructive_needs_confirm(desktop):
    from jarvis.tools.actions import run_action
    made, uia, handle = desktop
    verdict, result = run_action("uia_invoke", {"element_id": "e2"})
    # DESTRUCTIVE at autonomy L1 -> confirm (or deny); never silent allow
    assert verdict in ("confirm", "deny"), (verdict, result)
