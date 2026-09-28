"""Interpret configured lifecycle hooks around role pipeline phases."""

from __future__ import annotations

import importlib
from typing import Any, Callable

from .role_directory import lifecycle_hooks


class RoleLifecycleInterpreterError(RuntimeError):
    """Raised when a configured lifecycle hook cannot be executed."""


def run_lifecycle_phase(
    phase: str,
    *,
    context: dict[str, Any],
    directory: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    outputs = {}
    for hook in lifecycle_hooks(directory=directory):
        if str(hook.get("phase") or "") != phase:
            continue
        output_key = str(hook["output_key"])
        side_effects = list(hook.get("side_effects") or [])
        if side_effects and _resolve_binding(hook.get("permission"), context) is not True:
            result = {
                "status": "skipped",
                "reason": "side effect permission denied",
                "side_effects": side_effects,
            }
            outputs[output_key] = result
            context[output_key] = result
            continue
        function = _load_callable(str(hook.get("callable") or ""))
        kwargs = {
            str(name): _resolve_binding(value, context)
            for name, value in dict(hook.get("bindings") or {}).items()
        }
        result = function(**kwargs)
        if not isinstance(result, dict):
            raise RoleLifecycleInterpreterError(f"lifecycle hook returned non-object: {hook.get('hook_id')}")
        outputs[output_key] = result
        context[output_key] = result
    return outputs


def _resolve_binding(value: Any, context: dict[str, Any]) -> Any:
    if not isinstance(value, str) or not value.startswith("$"):
        return value
    if value.startswith("$artifact_type:"):
        artifact_type = value.split(":", 1)[1]
        for artifact in dict(context.get("artifacts") or {}).values():
            if isinstance(artifact, dict) and artifact.get("artifact_type") == artifact_type:
                return artifact
        return None
    current: Any = context
    for part in value[1:].split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            return None
    return current


def _load_callable(spec: str) -> Callable[..., Any]:
    if ":" not in spec:
        raise RoleLifecycleInterpreterError(f"lifecycle hook must be module:function: {spec}")
    module_name, function_name = spec.split(":", 1)
    function = getattr(importlib.import_module(module_name), function_name, None)
    if not callable(function):
        raise RoleLifecycleInterpreterError(f"lifecycle hook is not callable: {spec}")
    return function
