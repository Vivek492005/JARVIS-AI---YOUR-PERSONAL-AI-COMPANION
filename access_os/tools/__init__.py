"""Tool package: registry framework (Task 1.2) + specs.

Importing this package wires every tool spec: the framework lives in
:mod:`access_os.tools.registry`, the specs are registered by
:mod:`access_os.actions` (the single home for handlers), which is imported
below for its registration side effect.
"""

from .registry import REGISTRY, Risk, ToolSpec, function_schemas, resolve, tool

# Registers all ToolSpecs (imports actions for its _register_tools() call).
from access_os import actions as _actions  # noqa: E402,F401

__all__ = ["REGISTRY", "Risk", "ToolSpec", "function_schemas", "resolve", "tool"]
