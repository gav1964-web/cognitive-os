from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any


def find_init(source: str, class_name: str) -> ast.FunctionDef | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == "__init__":
                    return child
    return None


def source_for_row(root: Path, row: dict[str, Any]) -> str | None:
    path = root / str(row.get("project_root") or "") / str(row.get("path") or "")
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def candidate_key(row: dict[str, Any]) -> str:
    project = row.get("canonical_project") or row.get("project")
    target = f"{row.get('path')}:{row.get('class_name')}.__init__"
    return f"{project}::{target}"


def applied_target_keys(ledger: dict[str, Any]) -> set[str]:
    return {
        f"{dict(row).get('project')}::{dict(row).get('target')}"
        for row in ledger.get("cases") or []
        if isinstance(row, dict) and row.get("status") == "applied_active_kb"
    }


def read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload
