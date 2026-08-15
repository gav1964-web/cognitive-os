"""Config-backed effect-module stubs for source-isolated acceptance."""

from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from typing import Any, Iterator

from .executable_acceptance_policy import source_isolation_policy

_MISSING = object()


@contextmanager
def configured_effect_stubs(imported_modules: set[str]) -> Iterator[list[str]]:
    profiles = dict(source_isolation_policy().get("effect_module_stubs") or {})
    selected = {name: dict(profiles[name]) for name in imported_modules if name in profiles}
    saved = {name: sys.modules.get(name, _MISSING) for name in selected}
    try:
        for name, profile in selected.items():
            sys.modules[name] = _stub_module(name, profile)
        yield sorted(selected)
    finally:
        for name, previous in saved.items():
            if previous is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def _stub_module(name: str, profile: dict[str, Any]) -> types.ModuleType:
    module = types.ModuleType(name)
    for attr, value in dict(profile.get("attributes") or {}).items():
        setattr(module, str(attr), _stub_value(value, f"{name}.{attr}"))
    return module


def _stub_value(value: Any, label: str) -> Any:
    if isinstance(value, dict) and value.get("__fixture__") == "callable_object_noop":
        return _NoopObject(label)
    return value


class _NoopObject:
    def __init__(self, label: str):
        self.label = label

    def __call__(self, *args: Any, **kwargs: Any) -> "_NoopObject":
        return self

    def __getattr__(self, name: str) -> "_NoopObject":
        return _NoopObject(f"{self.label}.{name}")

    def __bool__(self) -> bool:
        return False
