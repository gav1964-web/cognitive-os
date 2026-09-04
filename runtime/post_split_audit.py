"""Diagnose mechanically split modules after source-size cleanup."""

from __future__ import annotations

import ast
from collections import Counter
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any


FACADE_MARKERS = (
    "Stable facade for split",
    "_PART_NAMES",
    "importlib.import_module",
)

SOURCE_ROOTS = ("runtime", "tools", "plugins", "tests")


def run_post_split_audit(*, root: Path, source_roots: tuple[str, ...] = SOURCE_ROOTS) -> dict[str, Any]:
    root = root.resolve()
    files = [
        path
        for source_root in source_roots
        for path in _python_files(root / source_root)
    ]
    facades = [_facade_row(root, path) for path in files if _is_split_facade(path)]
    helper_tests = [_helper_test_row(root, path) for path in files if _uses_helper_import(path)]
    by_root = Counter(row["source_root"] for row in facades)
    return {
        "artifact_type": "PostSplitAudit",
        "schema_version": "post_split_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "source_roots": list(source_roots),
        "facade_count": len(facades),
        "helper_backed_test_count": len(helper_tests),
        "facade_summary_by_root": dict(sorted(by_root.items())),
        "recommended_next_actions": _recommended_next_actions(facades, helper_tests),
        "facades": facades,
        "helper_backed_tests": helper_tests,
        "source_apply": False,
        "kb_promotion": False,
    }


def _facade_row(root: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    part_names = _part_names(path)
    return {
        "path": relative,
        "source_root": relative.split("/", 1)[0],
        "part_count": len(part_names),
        "parts": part_names,
        "classification": "mechanical_facade",
        "recommended_action": _facade_recommendation(relative, part_names),
    }


def _helper_test_row(root: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    return {
        "path": relative,
        "source_root": relative.split("/", 1)[0],
        "classification": "helper_backed_split_test",
        "recommended_action": "keep scenarios split; promote repeated builders into explicit test factories when edited next",
    }


def _recommended_next_actions(facades: list[dict[str, Any]], helper_tests: list[dict[str, Any]]) -> list[str]:
    actions = []
    if facades:
        actions.append("review mechanical facades and move cohesive policy/discovery/check code into named modules")
    if helper_tests:
        actions.append("keep helper-backed test suites under the line limit and avoid rebuilding monolithic tests")
    actions.append("treat post-split audit as design debt, while source_line_limit_gate remains the hard blocker")
    return actions


def _is_split_facade(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return all(marker in text for marker in FACADE_MARKERS)


def _uses_helper_import(path: Path) -> bool:
    if not path.name.startswith("test_"):
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "from tests.runtime." in text and "_helpers import *" in text


def _part_names(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None
    if tree is not None:
        names = _part_names_from_ast(tree)
        if names:
            return names
    names = []
    for line in text.splitlines():
        stripped = line.strip().strip(",").strip("\"'")
        if "_part" in stripped and not stripped.startswith("_PART") and " " not in stripped:
            names.append(stripped)
    return names


def _part_names_from_ast(tree: ast.AST) -> list[str]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "_PART_NAMES" for target in node.targets):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            return []
        values = []
        for item in node.value.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                values.append(item.value)
        return values
    return []


def _facade_recommendation(relative: str, part_names: list[str]) -> str:
    if relative.startswith("tools/"):
        return "keep CLI facade thin; move reusable case execution logic into runtime or named tool helper modules"
    if relative.startswith("runtime/"):
        return "replace mechanical part names with cohesive policy/interpreter modules when behavior changes next"
    return "review split boundaries before adding new behavior"


def _python_files(base: Path):
    if not base.exists():
        return
    if base.is_file() and base.suffix == ".py":
        yield base
        return
    for current, dirnames, filenames in os.walk(base):
        current_path = Path(current)
        dirnames[:] = [
            name
            for name in dirnames
            if _authoritative_source((current_path / name).relative_to(base))
        ]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = current_path / filename
            if _authoritative_source(path.relative_to(base)):
                yield path


def _authoritative_source(path: Path) -> bool:
    excluded = {
        ".git",
        ".pytest_cache",
        "__pycache__",
        "artifacts",
        "benchmark_corpora",
        "benchmarks",
        "generated",
        "venv",
        ".venv",
    }
    return not any(part in excluded or part.startswith(".pytest-tmp") for part in path.parts)
