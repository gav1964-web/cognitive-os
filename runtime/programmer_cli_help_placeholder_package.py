"""Sandbox package builder for the CLI type-placeholder reducer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .patch_synthesis_policy import cli_help_type_placeholder_contract_recipe
from .programmer_cli_help_placeholder_patch import cli_help_placeholder_patch
from .programmer_patch_synthesizer_common import NO_PATCH, _copy_project, _patch_result


def cli_help_placeholder_package(
    *, execution_dir: Path, project_dir: Path, target: str,
    path_text: str, symbol: str,
) -> dict[str, Any]:
    recipe = cli_help_type_placeholder_contract_recipe()
    if not recipe:
        return {**NO_PATCH, "reason": "cli_help_placeholder_recipe_disabled"}
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
    patch = cli_help_placeholder_patch(original, symbol=symbol, recipe=recipe)
    if patch is None:
        return {**NO_PATCH, "reason": "cli_help_placeholder_pattern_not_proven"}
    patched = str(patch["source"])
    source_path.write_text(patched, encoding="utf-8")
    return _patch_result(
        recipe=recipe,
        sandbox_project=sandbox_project,
        path_text=path_text,
        target=target,
        original=original,
        patched=patched,
        operation={
            "artifact_type": "PatchOperation",
            "kind": str(recipe.get("operation_kind") or "add_cli_int_help_placeholder"),
            "target": target,
            "file": path_text,
            "existing_type": patch["existing_type"],
            "added_type": patch["added_type"],
            "added_placeholder": patch["added_placeholder"],
        },
    )
