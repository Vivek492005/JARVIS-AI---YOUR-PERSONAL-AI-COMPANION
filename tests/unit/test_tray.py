"""Tests for tray + global hotkey summon (Phase 7 exit criteria). Headless."""

import sys

sys.path.insert(0, "src")

from jarvis.hud.tray import (
    FakeHotkeyBackend,
    FakeTrayBackend,
    HotkeySummon,
    KeyboardBackend,
    PystrayBackend,
    TrayController,
)


def test_tray_menu_wires_callbacks():
    fired = []
    tray = TrayController(
        backend=FakeTrayBackend(),
        on_show=lambda: fired.append("show"),
        on_summon=lambda: fired.append("summon"),
        on_quit=lambda: fired.append("quit"),
    )
    assert tray.available is True
    tray.run()
    labels = [label for label, _ in tray.backend.menu]
    assert labels == ["Show HUD", "Summon (wake)", "Quit"]
    for _, action in tray.backend.menu:
        action()
    assert fired == ["show", "summon", "quit"]
    assert tray.backend.stopped is True  # Quit also stops the backend


def test_tray_unavailable_backend_does_not_raise():
    tray = TrayController(backend=PystrayBackend())  # not installed here
    assert tray.available is False
    tray.run()  # logs + returns, no crash
    tray.stop()


def test_hotkey_fires_summon():
    fired = []
    backend = FakeHotkeyBackend()
    summon = HotkeySummon(on_summon=lambda: fired.append(1),
                          hotkey="ctrl+alt+j", backend=backend)
    summon.start()
    assert backend.registered and backend.registered[0][0] == "ctrl+alt+j"
    backend.fire("ctrl+alt+j")
    assert fired == [1]
    summon.stop()
    assert backend.cleared is True


def test_hotkey_unavailable_does_not_raise():
    summon = HotkeySummon(on_summon=lambda: None,
                          backend=KeyboardBackend())  # not installed here
    assert summon.available is False
    summon.start()
    summon.stop()


def test_hotkey_default_from_config():
    summon = HotkeySummon(on_summon=lambda: None,
                          backend=FakeHotkeyBackend())
    assert summon.hotkey == "ctrl+alt+j"
