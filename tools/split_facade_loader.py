"""Compatibility loader for legacy split modules with collision checks."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from types import ModuleType
from typing import Any


class SplitFacadeCollisionError(RuntimeError):
    """Raised when two split parts own the same undeclared symbol."""


def load_split_namespace(
    package: str,
    part_names: list[str],
    *,
    allowed_collisions: set[str] | None = None,
) -> tuple[list[ModuleType], dict[str, Any], list[str]]:
    parts = [importlib.import_module(f"{package}.{name}") for name in part_names]
    owners: dict[str, str] = {}
    collisions = []
    allowed = allowed_collisions or set()
    for part in parts:
        for name in _owned_names(part):
            previous = owners.get(name)
            if previous is not None and previous != part.__name__:
                collisions.append(name)
            owners[name] = part.__name__
    unexpected = sorted(set(collisions) - allowed)
    if unexpected:
        raise SplitFacadeCollisionError(
            f"split facade has conflicting owned symbols: {', '.join(unexpected)}"
        )

    merged: dict[str, Any] = {}
    for part in parts:
        merged.update({key: value for key, value in vars(part).items() if not key.startswith("__")})
    for part in parts:
        vars(part).update(merged)
    return parts, merged, sorted(set(collisions))


def _owned_names(module: ModuleType) -> set[str]:
    path = getattr(module, "__file__", None)
    if not path:
        return set()
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.update(target.id for target in targets if isinstance(target, ast.Name))
    return names
