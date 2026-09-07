"""Sandbox package builder for explicitly authorized training replay."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .patch_synthesis_policy import training_repair_recipe
from .programmer_patch_synthesizer_common import NO_PATCH, _copy_project, _patch_result
from .programmer_training_repair_patch import training_repair_patch


def training_repair_package(
    *, execution_dir: Path, project_dir: Path, target: str, path_text: str,
    symbol: str, operation_kind: str,
) -> dict[str, Any]:
    recipe = training_repair_recipe(operation_kind)
    if not recipe:
        return {**NO_PATCH, "reason": "training_repair_recipe_disabled"}
    sandbox_project = execution_dir / "patch_sandbox" / "project"
    _copy_project(project_dir, sandbox_project)
    source_path = (sandbox_project / path_text).resolve()
    try:
        source_path.relative_to(sandbox_project.resolve())
    except ValueError:
        return {"status": "blocked", "reason": "target_outside_sandbox", "patches": []}
    if not source_path.is_file():
        return {"status": "blocked", "reason": "target_file_missing_in_sandbox", "patches": []}
    original = source_path.read_text(encoding="utf-8")
    patch = training_repair_patch(
        original, symbol=symbol, operation_kind=operation_kind, recipe=recipe
    )
    if patch is None:
        return {**NO_PATCH, "reason": "training_repair_source_precondition_not_proven"}
    patched = str(patch["source"])
    source_path.write_text(patched, encoding="utf-8")
    return _patch_result(
        recipe=recipe, sandbox_project=sandbox_project, path_text=path_text,
        target=target, original=original, patched=patched,
        operation={
            "artifact_type": "PatchOperation",
            "kind": operation_kind,
            "target": target,
            "file": path_text,
            "authority": "explicit_training_replay",
            "source_precondition": patch["source_precondition"],
            "affected_symbols": list(patch.get("affected_symbols") or [symbol]),
        },
    )
