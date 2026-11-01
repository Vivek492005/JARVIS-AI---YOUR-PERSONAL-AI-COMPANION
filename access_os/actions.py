"""Deprecated compatibility shim (Phase 2, v0.4.0).

``access_os.actions`` moved to ``jarvis.tools.actions``. Import from ``jarvis.tools.actions`` instead —
this shim will be removed in v1.0.0.

The shim is a transparent proxy: the real module's public attributes are
mirrored into this module's ``__dict__`` at import time, and every later
read/write/delete is forwarded to the real module. That keeps
``mock.patch("access_os.actions....")`` and ``monkeypatch.setattr`` working
exactly as before the move (including pytest's ``__dict__``-based undo).
"""
import sys as _sys
import warnings as _warnings
import importlib as _importlib


class _ShimProxy(_sys.modules[__name__].__class__):
    """Module subclass forwarding attribute access to the real module."""

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return getattr(self.__dict__["_target"], name)

    def __setattr__(self, name, value):
        if name == "_target" or (name.startswith("__") and name.endswith("__")):
            object.__setattr__(self, name, value)
        else:
            setattr(self.__dict__["_target"], name, value)

    def __delattr__(self, name):
        if name == "_target" or (name.startswith("__") and name.endswith("__")):
            object.__delattr__(self, name)
        else:
            delattr(self.__dict__["_target"], name)

    def __dir__(self):
        return sorted(set(super().__dir__()) | set(dir(self.__dict__["_target"])))


_warnings.warn(
    "access_os.actions is deprecated; use jarvis.tools.actions instead",
    DeprecationWarning,
    stacklevel=2,
)

_mod = _sys.modules[__name__]
_target = _importlib.import_module("jarvis.tools.actions")
object.__setattr__(_mod, "_target", _target)
# Mirror public attributes so `target.__dict__` lookups (pytest's undo,
# mock's create detection) see the same state as the real module.
for _name in dir(_target):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    _mod.__dict__[_name] = getattr(_target, _name)
del _name
_mod.__class__ = _ShimProxy
