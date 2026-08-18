"""Shared normalization and shape gates for initial and repair L4.5 candidates."""

from __future__ import annotations

from typing import Any

from .programmer_structured_edit import replacement_shape_errors


def normalize_recipe(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("patch_recipe_hypothesis") or payload.get("patch_recipe") or {}
    recipe = raw if isinstance(raw, dict) else {}
    diff = recipe.get("diff") or payload.get("diff") or []
    diff_lines = diff.splitlines() if isinstance(diff, str) else list(diff)
    return {
        "recipe_type": str(recipe.get("recipe_type") or "")[:80],
        "target_symbol": str(recipe.get("target_symbol") or payload.get("target_symbol") or "")[:240],
        "edit_format": str(recipe.get("edit_format") or "unified_diff")[:40],
        "replacement_source": str(recipe.get("replacement_source") or "")[:8000],
        "summary": str(recipe.get("summary") or "")[:500],
        "diff": [str(item)[:1000] for item in diff_lines[:80]],
        "verification_hint": str(recipe.get("verification_hint") or "")[:500],
    }


def build_candidate_contract(
    *, llm: dict[str, Any], target: str, source_excerpt: str, authority: str, unavailable_reason: str
) -> dict[str, Any]:
    recipe = dict(llm.get("patch_recipe_hypothesis") or {})
    if llm.get("status") != "proposed" or llm.get("action") != "propose_patch_recipe":
        return {"status": "not_available", "reason": unavailable_reason}
    errors = candidate_errors(recipe, target, source_excerpt)
    return {
        "artifact_type": "SandboxPatchCandidate",
        "status": "blocked_invalid_candidate" if errors else "candidate_ready_for_sandbox_attempt",
        "authority": authority,
        "errors": errors,
        "target": target,
        "recipe_type": recipe.get("recipe_type"),
        "edit_format": recipe.get("edit_format"),
        "diff_line_count": len(list(recipe.get("diff") or [])),
        "replacement_line_count": len(str(recipe.get("replacement_source") or "").splitlines()),
    }


def candidate_errors(recipe: dict[str, Any], target: str, source_excerpt: str) -> list[str]:
    errors: list[str] = []
    path_text = target.split(":", 1)[0]
    if recipe.get("target_symbol") != target:
        errors.append("target_symbol_mismatch")
    if not str(recipe.get("recipe_type") or ""):
        errors.append("missing_recipe_type")
    replacement = str(recipe.get("replacement_source") or "")
    diff = [str(item) for item in list(recipe.get("diff") or [])]
    if replacement:
        errors.extend(replacement_shape_errors(replacement, target, source_excerpt))
    elif not diff:
        errors.append("missing_edit_payload")
    if diff and path_text and not any(path_text in line for line in diff[:10]):
        errors.append("diff_does_not_reference_target_file")
    if any(line.startswith(("--- /", "+++ /")) for line in diff):
        errors.append("absolute_diff_path_forbidden")
    return errors
