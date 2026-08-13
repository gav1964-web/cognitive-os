"""Evidence-bound temporary contract profile synthesis."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

from .self_improvement_profile_families import family_profile, recognize_contract_family


def synthesize_contract_profile(project_dir: Path, source: str) -> dict[str, Any] | None:
    """Recognize a supported contract family from source evidence, never LLM scoring."""
    path_text, separator, symbol = source.partition(":")
    path = (project_dir / path_text).resolve()
    if not separator or not _within(path, project_dir.resolve()) or not path.is_file():
        return None
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError):
        return None
    node = _function(tree, symbol)
    if node is None:
        return None
    return _profile_from_node(path_text, symbol, node)


def _profile_from_node(
    path_text: str, symbol: str, node: ast.AsyncFunctionDef | ast.FunctionDef
) -> dict[str, Any] | None:
    recognized = recognize_contract_family(node)
    if recognized is None:
        return None
    family_id, evidence = recognized
    identity = hashlib.sha256(f"{path_text}:{symbol}".encode()).hexdigest()[:12]
    return {
        **family_profile(family_id, evidence),
        "id": f"training_{family_id}_{identity}",
        "symbols": [symbol.lower()],
        "path_contains_any": [path_text.replace("\\", "/").lower()],
    }


def discover_contract_profile_candidates(
    project_dir: Path, *, limit: int = 20, max_files: int = 800, max_file_bytes: int = 500_000
) -> list[dict[str, Any]]:
    """Discover exact source targets accepted by the current typed recognizer."""
    candidates: list[dict[str, Any]] = []
    paths = sorted(project_dir.rglob("*.py"))[: max(0, max_files)]
    for path in paths:
        if any(part in {".git", ".venv", "venv", "node_modules"} for part in path.parts):
            continue
        try:
            if path.stat().st_size > max_file_bytes:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError):
            continue
        relative = path.relative_to(project_dir).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            source = f"{relative}:{node.name}"
            profile = _profile_from_node(relative, node.name, node)
            if profile:
                candidates.append({"source": source, "profile": profile})
                if len(candidates) >= max(0, limit):
                    return candidates
    return candidates


def _function(tree: ast.AST, symbol: str) -> ast.AsyncFunctionDef | ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name.lower() == symbol.lower():
            return node
    return None


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
