"""Tests for Phase 5.7 app adapters."""

import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, "tests")

from jarvis.perception.apps import (  # noqa: E402
    OfficeAdapter,
    SpotifyAdapter,
    VSCodeAdapter,
    apply_setting,
    list_settings,
)
from jarvis.tools.registry import REGISTRY, Risk  # noqa: E402
from fakes.fake_desktop import install_fake_desktop, uninstall_fake_desktop  # noqa: E402


@pytest.fixture()
def desktop():
    made = install_fake_desktop()
    yield made
    uninstall_fake_desktop()


def test_vscode_adapter(desktop):
    made = desktop
    out = VSCodeAdapter().open_path("C:/proj")
    assert "VS Code" in out
    assert ("vscode.open_path", ("C:/proj",)) in made["apps"].calls


def test_vscode_task(desktop):
    made = desktop
    VSCodeAdapter().run_task("build", "C:/proj")
    assert ("vscode.run_task", ("build", "C:/proj")) in made["apps"].calls


def test_office_adapter(desktop):
    assert "opened" in OfficeAdapter().open_document("doc.docx")
    assert "A1" in OfficeAdapter().read("s.xlsx", "Sheet1", "A1:B2")
    assert "saved" in OfficeAdapter().save("doc.docx")


def test_spotify_adapter(desktop):
    assert "spotify play" in SpotifyAdapter().control("play")
    assert "unknown spotify action" in SpotifyAdapter().control("explode")


def test_apply_setting_allowlisted():
    out = apply_setting("brightness_up")
    assert "setting applied: brightness_up" in out


def test_apply_setting_unknown_refused():
    out = apply_setting("format_c_drive")
    assert "unknown setting" in out
    assert "allowed" in out


def test_list_settings_only_allowlisted():
    settings = list_settings()
    assert "wifi_toggle" in settings
    assert "format" not in settings


def test_tools_registered():
    assert REGISTRY["vscode_open"].risk == Risk.REVERSIBLE
    assert REGISTRY["office_read"].risk == Risk.READ
    assert REGISTRY["office_read"].carries_external_data is True
    assert REGISTRY["spotify"].risk == Risk.REVERSIBLE
    assert REGISTRY["system_settings"].risk == Risk.REVERSIBLE


def test_run_action_spotify_gated(desktop):
    from jarvis.tools.actions import run_action

    verdict, result = run_action("spotify", {"action": "pause"})
    assert verdict in ("allow", "confirm"), (verdict, result)
