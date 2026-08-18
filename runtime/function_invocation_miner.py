"""Mine anonymized call/oracle shapes from Python project tests."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import Any

from .function_invocation_patterns import load_function_invocation_patterns


def mine_function_invocations(project_roots: list[Path], *, max_files_per_project: int = 500) -> dict[str, Any]:
    policy = dict(load_function_invocation_patterns().get("admission_policy") or {})
    observations: dict[tuple[str, str], list[int]] = defaultdict(list)
    for project_index, root in enumerate(project_roots):
        if not root.is_dir():
            continue
        for path in list(_test_files(root))[:max_files_per_project]:
            for shape in _file_shapes(path):
                observations[shape].append(project_index)
    rows = []
    min_projects = int(policy.get("minimum_distinct_projects") or 3)
    min_observations = int(policy.get("minimum_observations") or 5)
    for (call_shape, oracle), projects in sorted(observations.items()):
        distinct = len(set(projects))
        count = len(projects)
        rows.append(
            {
                "call_shape": call_shape,
                "oracle": oracle,
                "observations": count,
                "distinct_projects": distinct,
                "promotion_eligible": (
                    oracle != "execution_only" and distinct >= min_projects and count >= min_observations
                ),
            }
        )
    return {
        "artifact_type": "FunctionInvocationMiningReport",
        "status": "ok",
        "project_count": sum(root.is_dir() for root in project_roots),
        "patterns": rows,
        "privacy": {"project_names_stored": False, "source_code_stored": False},
    }


def _test_files(root: Path):
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix().lower()
        if path.name.startswith("test_") or "/tests/" in f"/{rel}":
            yield path


def _file_shapes(path: Path) -> list[tuple[str, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return []
    parents = _parents(tree)
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _is_test_helper(node) or not _in_test_function(node, parents):
            continue
        rows.append((_call_shape(node), _oracle_shape(node, parents)))
    return rows


def _call_shape(node: ast.Call) -> str:
    args = [_value_shape(arg) for arg in node.args]
    kwargs = [_value_shape(item.value) for item in node.keywords if item.arg]
    binding = "mixed" if args and kwargs else "keyword" if kwargs else "positional"
    values = sorted({*args, *kwargs}) or ["empty"]
    return f"{binding}:{'+'.join(values)}"


def _value_shape(node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        return "literal"
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return "collection"
    if isinstance(node, ast.Dict):
        return "mapping"
    if isinstance(node, ast.Call):
        return "constructor"
    return "bound_value"


def _oracle_shape(node: ast.Call, parents: dict[ast.AST, ast.AST]) -> str:
    parent = parents.get(node)
    if isinstance(parent, ast.Await):
        parent = parents.get(parent)
    if isinstance(parent, ast.Compare):
        return "equality"
    if isinstance(parent, ast.Assert):
        return "truthiness"
    return "execution_only"


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _in_test_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    current = parents.get(node)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name.startswith("test_")
        current = parents.get(current)
    return False


def _is_test_helper(node: ast.Call) -> bool:
    name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
    return name in {"fixture", "parametrize", "raises", "mark"}
