"""Target resolution and AST facts for project-development source evidence."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any


def collect_python_target_facts(project_dir: Path, target: str) -> dict[str, Any]:
    resolved = resolve_python_target(project_dir, target)
    if resolved["path"] is None:
        return {"source_backed": False, "reason": resolved["reason"]}
    path = resolved["path"]
    symbol = str(resolved["symbol"])
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return {"source_backed": False, "reason": "target_source_unreadable"}
    function = _target_function(tree, symbol)
    if function is None:
        return {"source_backed": False, "reason": "target_symbol_missing"}
    owner = _target_owner_class(tree, symbol)
    parents = {
        child: parent
        for parent in ast.walk(function)
        for child in ast.iter_child_nodes(parent)
    }
    loops = [node for node in ast.walk(function) if isinstance(node, (ast.For, ast.AsyncFor))]
    maximum_depth = max((_loop_depth(node, parents) for node in loops), default=0)
    dict_append_sites = sum(
        1
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "append"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Dict)
    )
    facts = {
        "source_backed": True,
        "path": resolved["relative_path"],
        "symbol": symbol,
        "line_start": int(function.lineno),
        "line_end": int(getattr(function, "end_lineno", function.lineno)),
        "loop_count": len(loops),
        "maximum_loop_depth": maximum_depth,
        "dict_append_sites": dict_append_sites,
    }
    if owner is not None and function.name == "__init__":
        constructor_parameters = [arg.arg for arg in function.args.args if arg.arg not in {"self", "cls"}]
        stored_parameters = sorted({
            node.value.id
            for node in ast.walk(function)
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Name)
            and node.value.id in constructor_parameters
            and any(
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                for target in node.targets
            )
        })
        super_init = next(
            (
                node for node in ast.walk(function)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "__init__"
                and isinstance(node.func.value, ast.Call)
                and isinstance(node.func.value.func, ast.Name)
                and node.func.value.func.id == "super"
            ),
            None,
        )
        replayed = (
            [arg.id for arg in super_init.args if isinstance(arg, ast.Name)]
            if super_init is not None and all(isinstance(arg, ast.Name) for arg in super_init.args)
            else []
        )
        facts.update({
            "owner_class": owner.name,
            "owner_bases": [_base_name(base) for base in owner.bases if _base_name(base)],
            "custom_exception_constructor": any(
                _base_name(base).endswith(("Error", "Exception")) for base in owner.bases if _base_name(base)
            ),
            "constructor_parameters": constructor_parameters,
            "stored_constructor_parameters": stored_parameters,
            "base_exception_direct_parameters": replayed,
            "base_exception_replays_constructor_parameters": replayed == constructor_parameters,
            "has_reduce_method": any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__reduce__"
                for node in owner.body
            ),
        })
    return facts


def _target_function(
    tree: ast.Module, symbol: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    parts = symbol.split(".")
    statements = _module_scope_statements(tree.body)
    if len(parts) == 1:
        return next(
            (
                node for node in statements
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == parts[0]
            ),
            None,
        )
    if len(parts) == 2:
        owner = next(
            (node for node in statements if isinstance(node, ast.ClassDef) and node.name == parts[0]),
            None,
        )
        if owner is not None:
            return next(
                (
                    node for node in _module_scope_statements(owner.body)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == parts[1]
                ),
                None,
            )
    return None


def _target_owner_class(tree: ast.Module, symbol: str) -> ast.ClassDef | None:
    parts = symbol.split(".")
    if len(parts) != 2:
        return None
    return next(
        (
            node for node in _module_scope_statements(tree.body)
            if isinstance(node, ast.ClassDef) and node.name == parts[0]
        ),
        None,
    )


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _base_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _module_scope_statements(statements: list[ast.stmt]) -> list[ast.stmt]:
    result: list[ast.stmt] = []
    for statement in statements:
        result.append(statement)
        nested: list[ast.stmt] = []
        if isinstance(statement, (ast.If, ast.For, ast.AsyncFor, ast.While)):
            nested = [*statement.body, *statement.orelse]
        elif isinstance(statement, (ast.With, ast.AsyncWith)):
            nested = list(statement.body)
        elif isinstance(statement, ast.Try):
            nested = [
                *statement.body,
                *statement.orelse,
                *statement.finalbody,
                *(child for handler in statement.handlers for child in handler.body),
            ]
        elif isinstance(statement, ast.Match):
            nested = [child for case in statement.cases for child in case.body]
        if nested:
            result.extend(_module_scope_statements(nested))
    return result


def target_source_digest(project_dir: Path, target: str) -> str | None:
    resolved = resolve_python_target(project_dir, target)
    path = resolved["path"]
    if path is None:
        return None
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def resolve_python_target(project_dir: Path, target: str) -> dict[str, Any]:
    if ":" not in target:
        return {"path": None, "reason": "target_missing_symbol"}
    path_text, symbol = target.split(":", 1)
    root = project_dir.resolve()
    path = (root / path_text).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return {"path": None, "reason": "target_outside_project"}
    if not path.is_file():
        return {"path": None, "reason": "target_file_missing"}
    return {
        "path": path,
        "relative_path": path_text,
        "symbol": symbol,
        "reason": None,
    }


def _loop_depth(node: ast.For | ast.AsyncFor, parents: dict[ast.AST, ast.AST]) -> int:
    depth = 1
    current: ast.AST = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.For, ast.AsyncFor)):
            depth += 1
    return depth
