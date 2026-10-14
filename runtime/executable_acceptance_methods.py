"""Method fixture support for executable acceptance harnesses."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

from .executable_acceptance_materializers import materialize
from .executable_acceptance_policy import method_fixture_policy


def load_method_callable(path: Path, symbol: str, module: object | None) -> dict[str, Any]:
    policy = method_fixture_policy()
    if not policy.get("enabled"):
        return {"callable": None, "detail": "method_fixture_policy_disabled"}
    match = _unique_method_match(path, symbol)
    if not match or module is None:
        return {"callable": None, "detail": "method_match_missing_or_module_unloaded"}
    class_name = match["class_name"]
    symbol = match["method_name"]
    runtime_symbol = runtime_method_name(class_name, symbol)
    cls = getattr(module, class_name, None)
    if cls is None:
        return {"callable": None, "detail": f"{class_name}.{symbol}: class_not_loaded"}
    member = getattr(cls, runtime_symbol, None)
    if callable(member) and _callable_accepts_without_self(member):
        return {"callable": member, "method": match}
    instance = _method_instance(cls, policy)
    if instance is None:
        return {"callable": None, "detail": f"{class_name}.{symbol}: instance_fixture_required"}
    attrs = dict(dict(policy.get("instance_attribute_profiles") or {}).get(f"{class_name}.{symbol}") or {})
    for key, value in attrs.items():
        try:
            setattr(instance, key, materialize(value))
        except Exception as exc:
            return {"callable": None, "detail": f"{class_name}.{symbol}: instance_attr_unsettable:{key}:{type(exc).__name__}"}
    bound = getattr(instance, runtime_symbol, None)
    if callable(bound):
        return {"callable": bound, "method": match, "instance_attributes": attrs}
    return {"callable": None, "detail": f"{class_name}.{symbol}: method_not_bound"}


def method_detail(method: dict[str, Any]) -> str:
    match = dict(method.get("method") or {})
    return f"{str(match.get('class_name') or '?')}.{str(match.get('method_name') or '?')}"


def _method_instance(cls: object, policy: dict[str, Any]) -> object | None:
    if policy.get("default_constructor_first"):
        try:
            return cls()
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
                raise
    if policy.get("safe_uninitialized_instance"):
        try:
            return object.__new__(cls)
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
                raise
    return None


def _callable_accepts_without_self(func: object) -> bool:
    try:
        params = list(inspect.signature(func).parameters)
    except (TypeError, ValueError):
        return False
    return not params or params[0] not in {"self", "cls"}


def runtime_method_name(class_name: str, method_name: str) -> str:
    if method_name.startswith("__") and not method_name.endswith("__"):
        return f"_{class_name.lstrip('_')}{method_name}"
    return method_name


def _unique_method_match(path: Path, symbol: str) -> dict[str, str] | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    owner, separator, method_name = symbol.partition(".")
    method_name = method_name if separator else owner
    expected_owner = owner if separator else ""
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if expected_owner and node.name != expected_owner:
                continue
            matches.extend(
                {"class_name": node.name, "method_name": method_name}
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name
            )
    return matches[0] if len(matches) == 1 else None
