"""Tests for the gesture-confirm plugin (Task 7.8). Headless: fake controller."""

import sys
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, "src")

from jarvis.perception import gesture_gate
from jarvis.perception.gesture_gate import await_gesture, gesture_available


class FakeController:
    """Mimics the legacy GestureController API without a camera."""

    def __init__(self, fire=None):
        self.fire = fire  # "thumbs_up" | "thumbs_down" | None
        self.registered = []
        self.started = False
        self.stopped = False

    def register_gesture(self, name, callback, cooldown=1.0):
        self.registered.append(name)
        if self.fire == name:
            callback(SimpleNamespace(name=name))

    def unregister_gesture(self, name):
        if name in self.registered:
            self.registered.remove(name)

    def start(self, camera_index=0, max_retries=3):
        self.started = True
        return True

    def stop(self):
        self.stopped = True


def test_gesture_available_reports_missing_deps(monkeypatch):
    # Hermetic: force ImportError regardless of what other test modules
    # stuffed into sys.modules (integration/test_gesture_controller.py
    # installs MagicMock stand-ins for mediapipe/cv2).
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in ("mediapipe", "cv2", "numpy"):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    ok, reason = gesture_available()
    assert ok is False
    assert "mediapipe" in reason and "cv2" in reason


def test_await_gesture_unavailable_without_factory(monkeypatch):
    monkeypatch.setattr(gesture_gate, "gesture_available", lambda: (False, "nope"))
    assert await_gesture(controller_factory=None).startswith("unavailable")


def test_thumbs_up_means_haan():
    ctrl = FakeController(fire="thumbs_up")
    assert await_gesture(timeout_s=2.0, controller_factory=lambda: ctrl) == "haan"
    assert ctrl.stopped is True  # camera released


def test_thumbs_down_means_nahi():
    ctrl = FakeController(fire="thumbs_down")
    assert await_gesture(timeout_s=2.0, controller_factory=lambda: ctrl) == "nahi"
    assert ctrl.stopped is True


def test_no_gesture_means_timeout():
    ctrl = FakeController(fire=None)
    assert await_gesture(timeout_s=0.3, controller_factory=lambda: ctrl) == "timeout"
    assert ctrl.stopped is True


def test_controller_error_is_contained():
    class Boom:
        def register_gesture(self, *a, **k):
            raise RuntimeError("cam busy")

        def stop(self):
            pass

    assert await_gesture(timeout_s=1.0, controller_factory=Boom).startswith("unavailable")


def test_skill_manifest_loads():
    from jarvis.brain.skills.loader import load_manifest

    m = load_manifest(Path("skills/gesture-confirm"))
    assert m.name == "gesture-confirm"
    assert any(t.name == "gesture_confirm" for t in m.tools)
    assert any("camera" in p for p in (m.permissions or []))


def test_skill_tool_registers():
    # tool.py must exec without mediapipe installed (lazy import in gate).
    import importlib.util
    from jarvis.brain.skills.loader import load_manifest

    load_manifest(Path("skills/gesture-confirm"))  # validates the manifest
    registered = []
    spec = importlib.util.spec_from_file_location(
        "jarvis_skill_gesture_confirm", "skills/gesture-confirm/tool.py"
    )
    mod = importlib.util.module_from_spec(spec)
    mod.register_skill_tool = registered.append
    spec.loader.exec_module(mod)
    assert len(registered) == 1
    assert registered[0].name == "gesture_confirm"
    # handler degrades cleanly without the optional deps
    out = registered[0].handler({}, None, "")
    assert out.startswith("unavailable:")
