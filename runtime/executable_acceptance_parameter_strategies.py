"""Optional AST strategies admitted through bounded self-improvement trials."""

from __future__ import annotations

import ast
from typing import Any

Candidates = dict[str, list[tuple[int, Any, str]]]
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def add_parameter_strategy_samples(
    node: FunctionNode,
    parameters: set[str],
    candidates: Candidates,
    *,
    policy: dict[str, Any],
    priorities: dict[str, int],
) -> None:
    """Apply only strategies enabled by promoted policy."""
    if policy.get("nested_mapping_paths"):
        _nested_mapping_paths(node, parameters, candidates, priorities["required_mapping_keys"])
    if policy.get("callable_arity"):
        _callable_arity(node, parameters, candidates, priorities["parameter_callable"])
    if policy.get("derived_conversion"):
        _derived_conversion(node, parameters, candidates, priorities["conversion"])
    if policy.get("indexed_sequence"):
        _indexed_sequence(node, parameters, candidates, priorities["required_mapping_keys"])


def _nested_mapping_paths(
    node: FunctionNode, parameters: set[str], candidates: Candidates, priority: int
) -> None:
    trees: dict[str, dict[str, Any]] = {name: {} for name in parameters}
    for item in ast.walk(node):
        if not isinstance(item, ast.Subscript):
            continue
        path = _subscript_path(item, parameters)
        if len(path) < 3:
            continue
        current = trees[path[0]]
        for key in path[1:-1]:
            current = current.setdefault(key, {})
        current.setdefault(path[-1], [])
    for name, value in trees.items():
        if value:
            candidates[name].append(
                (priority + 1, value, "ast_strategy:nested_mapping_paths")
            )
    _iterated_mapping_paths(node, parameters, candidates, priority + 2)


def _iterated_mapping_paths(
    node: FunctionNode, parameters: set[str], candidates: Candidates, priority: int
) -> None:
    for loop in (item for item in ast.walk(node) if isinstance(item, ast.For)):
        if not isinstance(loop.target, ast.Name):
            continue
        source = _subscript_path(loop.iter, parameters)
        fields = {
            path[1]
            for item in ast.walk(loop)
            for path in [_subscript_path(item, {loop.target.id})]
            if len(path) == 2
        }
        if not source or not fields:
            continue
        value: Any = [{field: "sample" for field in sorted(fields)}]
        for key in reversed(source[1:]):
            value = {key: value}
        candidates[source[0]].append(
            (priority, value, "ast_strategy:iterated_mapping_paths")
        )
    for item in ast.walk(node):
        if not isinstance(item, (ast.Assign, ast.AnnAssign)):
            continue
        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
        alias = next((target.id for target in targets if isinstance(target, ast.Name)), "")
        call = item.value
        if not alias or not isinstance(call, ast.Call) or not call.args:
            continue
        source = _subscript_path(call.args[0], parameters)
        fields = {
            path[1]
            for child in ast.walk(node)
            for path in [_subscript_path(child, {alias})]
            if len(path) == 2
        }
        if source and fields:
            value = _nested_value(source[1:], [{field: "sample" for field in sorted(fields)}])
            candidates[source[0]].append(
                (priority, value, "ast_strategy:tabular_mapping_paths")
            )


def _nested_value(path: tuple[str, ...], leaf: Any) -> Any:
    value = leaf
    for key in reversed(path):
        value = {key: value}
    return value


def _subscript_path(node: ast.AST, parameters: set[str]) -> tuple[str, ...]:
    keys: list[str] = []
    current = node
    while isinstance(current, ast.Subscript):
        key = _literal(current.slice)
        if not isinstance(key, (str, int)):
            return ()
        if isinstance(key, str):
            keys.append(key)
        current = current.value
    if not isinstance(current, ast.Name) or current.id not in parameters:
        return ()
    return (current.id, *reversed(keys))


def _callable_arity(
    node: FunctionNode, parameters: set[str], candidates: Candidates, priority: int
) -> None:
    for item in ast.walk(node):
        if not isinstance(item, ast.Call) or not isinstance(item.func, ast.Name):
            continue
        if item.func.id not in parameters:
            continue
        fixture = "callable_noop" if not item.args and not item.keywords else "callable_identity"
        candidates[item.func.id].append(
            (priority + 1, {"__fixture__": fixture}, f"ast_strategy:callable_arity:{len(item.args)}")
        )


def _derived_conversion(
    node: FunctionNode, parameters: set[str], candidates: Candidates, priority: int
) -> None:
    origins: dict[str, set[str]] = {name: {name} for name in parameters}
    statements = list(ast.walk(node))
    for _ in range(min(12, len(statements))):
        changed = False
        for item in statements:
            if isinstance(item, (ast.Assign, ast.AnnAssign)):
                targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                changed |= _bind_targets(targets, _origins(item.value, origins), origins)
            elif isinstance(item, ast.For):
                changed |= _bind_targets([item.target], _origins(item.iter, origins), origins)
        if not changed:
            break
    for item in statements:
        if not _is_int_conversion(item):
            continue
        for name in sorted(_origins(item.args[0], origins) & parameters):
            candidates[name].append(
                (priority + 35, "1", "ast_strategy:derived_conversion:int")
            )


def _indexed_sequence(
    node: FunctionNode, parameters: set[str], candidates: Candidates, priority: int
) -> None:
    indices: dict[str, list[tuple[int, ...]]] = {name: [] for name in parameters}
    for item in ast.walk(node):
        path = _numeric_subscript_path(item, parameters)
        if path:
            indices[path[0]].append(path[1])
    for name, paths in indices.items():
        if not paths:
            continue
        depth = max(len(path) for path in paths)
        shape = [max((path[level] for path in paths if len(path) > level), default=0) + 1
                 for level in range(depth)]
        value: Any = 0
        for size in reversed(shape):
            value = [value for _ in range(size)]
        candidates[name].append(
            (priority + 3, value, "ast_strategy:indexed_sequence")
        )


def _numeric_subscript_path(
    node: ast.AST, parameters: set[str]
) -> tuple[str, tuple[int, ...]] | None:
    values: list[int] = []
    current = node
    while isinstance(current, ast.Subscript):
        value = _literal(current.slice)
        if not isinstance(value, int) or value < 0:
            return None
        values.append(value)
        current = current.value
    if not isinstance(current, ast.Name) or current.id not in parameters:
        return None
    return current.id, tuple(reversed(values))


def _bind_targets(
    targets: list[ast.AST], source: set[str], origins: dict[str, set[str]]
) -> bool:
    changed = False
    for target in targets:
        names = [item.id for item in ast.walk(target) if isinstance(item, ast.Name)]
        for name in names:
            before = set(origins.get(name, set()))
            origins.setdefault(name, set()).update(source)
            changed |= before != origins[name]
    return changed


def _origins(node: ast.AST, origins: dict[str, set[str]]) -> set[str]:
    return {
        origin
        for item in ast.walk(node)
        if isinstance(item, ast.Name)
        for origin in origins.get(item.id, set())
    }


def _is_int_conversion(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "int"
        and bool(node.args)
    )


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None
