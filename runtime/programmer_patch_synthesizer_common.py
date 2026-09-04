"""Shared patch-package helpers for deterministic programmer synthesis."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

NO_PATCH = {"status": "skipped", "reason": "no_supported_patch_pattern", "patches": []}

def _recovery_patch_digest(patches: list[dict[str, Any]], source_precondition_sha256: str) -> str:
    payload = {
        "source_precondition_sha256": source_precondition_sha256,
        "patches": patches,
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

def _patch_result(
    *,
    recipe: dict[str, Any],
    sandbox_project: Path,
    path_text: str,
    target: str,
    original: str,
    patched: str,
    operation: dict[str, Any],
) -> dict[str, Any]:
    diff = list(
        difflib.unified_diff(
            original.splitlines(),
            patched.splitlines(),
            fromfile=f"a/{path_text}",
            tofile=f"b/{path_text}",
            lineterm="",
        )
    )
    operation["diff"] = diff
    return {
        "status": str(recipe.get("status") or "prepared"),
        "reason": str(recipe.get("reason") or "deterministic_patch_synthesized"),
        "sandbox_project": sandbox_project.as_posix(),
        "patches": [operation],
    }

def _target_symbol(implementation_plan: dict[str, Any]) -> str:
    intent = dict(implementation_plan.get("patch_intent", {}))
    target = str(intent.get("target_symbol") or "")
    if target:
        return target
    return str(dict(implementation_plan.get("implementation_target", {})).get("candidate") or "")

def _expected_files(implementation_plan: dict[str, Any]) -> list[str]:
    return [str(item).split(":", 1)[0] for item in implementation_plan.get("expected_files", []) if item]

def _copy_project(project_dir: Path, sandbox_project: Path) -> None:
    if sandbox_project.exists():
        _remove_tree(sandbox_project)
    sandbox_project.mkdir(parents=True, exist_ok=True)
    ignored_dirs = {".git", "__pycache__", ".pytest_cache", "artifacts", "reports", "node_modules", ".venv", "venv"}
    for current, dirnames, filenames in os.walk(project_dir, onerror=lambda _exc: None):
        current_path = Path(current)
        dirnames[:] = [name for name in dirnames if name not in ignored_dirs]
        try:
            relative = current_path.relative_to(project_dir)
        except ValueError:
            continue
        destination_dir = sandbox_project / relative
        try:
            destination_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            dirnames[:] = []
            continue
        for filename in filenames:
            source = current_path / filename
            destination = destination_dir / filename
            try:
                shutil.copy2(source, destination)
            except OSError:
                continue

def _remove_tree(path: Path) -> None:
    def onerror(function: object, name: str, exc_info: object) -> None:
        try:
            os.chmod(name, 0o700)
            function(name)
        except OSError:
            pass

    shutil.rmtree(path, onerror=onerror)
