"""System tray + global hotkey summon (Phase 7 exit criteria).

Windows-only at runtime (needs a real desktop + system tray), implemented
behind injectable backends so everything is headless-testable:

- ``TrayController`` — tray icon with Show HUD / Summon / Quit menu.
- ``HotkeySummon`` — global hotkey (default from
  ``voice.push_to_talk_hotkey``, e.g. ctrl+alt+j) that fires ``on_summon``.

Real backends (``PystrayBackend``, ``KeyboardBackend``) lazily import their
optional third-party packages; when those aren't installed the controller
reports ``available() == False`` instead of crashing. Tests use
``FakeTrayBackend`` / ``FakeHotkeyBackend``.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

OnAction = Callable[[], None]


class TrayBackend:
    """Interface real (pystray) and fake backends implement."""

    def available(self) -> bool:
        return False

    def run(self, title: str, menu: List[tuple]) -> None:
        """Blocking: show the icon until quit. menu = [(label, action)]."""
        raise NotImplementedError

    def stop(self) -> None: ...


class PystrayBackend(TrayBackend):
    def available(self) -> bool:
        try:
            import pystray  # noqa: F401
            from PIL import Image  # noqa: F401

            return True
        except ImportError:
            return False

    def run(self, title: str, menu: List[tuple]) -> None:
        import pystray
        from PIL import Image, ImageDraw

        # Reuse the HUD orb look: dark rounded square + blue ring.
        img = Image.new("RGB", (64, 64), (11, 15, 20))
        d = ImageDraw.Draw(img)
        d.ellipse([10, 10, 54, 54], outline=(110, 168, 254), width=5)
        icon = pystray.Icon(
            title,
            img,
            title,
            menu=pystray.Menu(*[pystray.MenuItem(label, action) for label, action in menu]),
        )
        self._icon = icon
        icon.run()

    def stop(self) -> None:
        icon = getattr(self, "_icon", None)
        if icon is not None:
            icon.stop()


class FakeTrayBackend(TrayBackend):
    """Headless stand-in: records menu, never blocks."""

    def __init__(self) -> None:
        self.menu: List[tuple] = []
        self.ran = False
        self.stopped = False

    def available(self) -> bool:
        return True

    def run(self, title: str, menu: List[tuple]) -> None:
        self.menu = list(menu)
        self.ran = True

    def stop(self) -> None:
        self.stopped = True


class TrayController:
    """Tray icon driving HUD visibility + summon + quit."""

    def __init__(
        self,
        backend: Optional[TrayBackend] = None,
        on_show: Optional[OnAction] = None,
        on_summon: Optional[OnAction] = None,
        on_quit: Optional[OnAction] = None,
    ) -> None:
        self.backend = backend or PystrayBackend()
        self.on_show = on_show or (lambda: None)
        self.on_summon = on_summon or (lambda: None)
        self.on_quit = on_quit or (lambda: None)

    @property
    def available(self) -> bool:
        return self.backend.available()

    def run(self) -> None:
        if not self.available:
            logger.warning("tray: pystray/Pillow not installed — tray disabled")
            return
        self.backend.run(
            "JARVIS",
            [
                ("Open chat", lambda: self.on_show()),
                ("Summon (wake)", lambda: self.on_summon()),
                ("Quit", lambda: (self.on_quit(), self.backend.stop())),
            ],
        )

    def stop(self) -> None:
        self.backend.stop()


class HotkeyBackend:
    def available(self) -> bool:
        return False

    def register(self, hotkey: str, callback: OnAction) -> None:
        raise NotImplementedError

    def unregister_all(self) -> None: ...


class KeyboardBackend(HotkeyBackend):
    def available(self) -> bool:
        try:
            import keyboard  # noqa: F401

            return True
        except ImportError:
            return False

    def register(self, hotkey: str, callback: OnAction) -> None:
        import keyboard

        keyboard.add_hotkey(hotkey, callback)

    def unregister_all(self) -> None:
        if not self.available():
            return
        import keyboard

        keyboard.unhook_all_hotkeys()


class FakeHotkeyBackend(HotkeyBackend):
    def __init__(self) -> None:
        self.registered: List[tuple] = []
        self.cleared = False

    def available(self) -> bool:
        return True

    def register(self, hotkey: str, callback: OnAction) -> None:
        self.registered.append((hotkey, callback))

    def unregister_all(self) -> None:
        self.registered.clear()
        self.cleared = True

    def fire(self, hotkey: str) -> None:
        for hk, cb in self.registered:
            if hk == hotkey:
                cb()


class HotkeySummon:
    """Global hotkey → on_summon. Default from voice.push_to_talk_hotkey."""

    def __init__(
        self,
        on_summon: OnAction,
        hotkey: Optional[str] = None,
        backend: Optional[HotkeyBackend] = None,
    ) -> None:
        self.on_summon = on_summon
        self.backend = backend or KeyboardBackend()
        self.hotkey = hotkey or self._default_hotkey()

    @staticmethod
    def _default_hotkey() -> str:
        try:
            from jarvis.core.config import get_settings

            return get_settings().voice.push_to_talk_hotkey or "ctrl+alt+j"
        except Exception:
            return "ctrl+alt+j"

    @property
    def available(self) -> bool:
        return self.backend.available()

    def start(self) -> None:
        if not self.available:
            logger.warning("hotkey: 'keyboard' package not installed — global summon disabled")
            return
        self.backend.register(self.hotkey, self.on_summon)

    def stop(self) -> None:
        self.backend.unregister_all()
