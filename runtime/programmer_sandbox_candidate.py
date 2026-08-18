"""Apply reviewed LLM patch candidates inside a sandbox only."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from .programmer_patch_synthesizer import _copy_project
from .programmer_structured_edit import apply_structured_replacement


def apply_sandbox_patch_candidate(
    *,
    execution_dir: Path,
    project_dir: Path,
    implementation_plan: dict[str, Any],
    strategy: dict[str, Any],
    sandbox_name: str = "llm_patch_sandbox",
) -> dict[str, Any]:
    candidate = dict(strategy.get("sandbox_patch_candidate") or {})
    if candidate.get("status") != "candidate_ready_for_sandbox_attempt":
        return {"status": "not_applied", "reason": str(candidate.get("status") or "candidate_not_ready")}
    target = _target_symbol(implementation_plan)
    path_text = target.split(":", 1)[0]
    if not target or path_text not in _expected_files(implementation_plan):
        return {"status": "blocked", "reason": "target_not_in_expected_files"}
    recipe = dict(dict(strategy.get("llm_strategy") or {}).get("patch_recipe_hypothesis") or {})
    diff_lines = [str(item) for item in list(recipe.get("diff") or [])]
    replacement = str(recipe.get("replacement_source") or "")
    sandbox_project = execution_dir / sandbox_name / "project"
    _copy_project(project_dir, sandbox_project)
    source = (sandbox_project / path_text).resolve()
    try:
        source.relative_to(sandbox_project.resolve())
    except ValueError:
        return {"status": "blocked", "reason": "target_outside_sandbox"}
    if not source.is_file():
        return {"status": "blocked", "reason": "target_file_missing_in_sandbox"}
    original = source.read_text(encoding="utf-8")
    if replacement:
        patched, apply_reason = apply_structured_replacement(original, target, replacement)
    else:
        patched = _apply_unified_diff(original, diff_lines)
        apply_reason = "diff_apply_failed" if patched is None else "llm_patch_candidate_applied_in_sandbox"
    if patched is None:
        return {"status": "blocked", "reason": apply_reason or "diff_apply_failed", "sandbox_project": sandbox_project.as_posix()}
    if patched == original:
        return {"status": "blocked", "reason": "diff_noop", "sandbox_project": sandbox_project.as_posix()}
    source.write_text(patched, encoding="utf-8")
    return {
        "status": "applied_in_sandbox",
        "reason": apply_reason,
        "sandbox_project": sandbox_project.as_posix(),
        "patches": [
            {
                "artifact_type": "PatchOperation",
                "kind": str(recipe.get("recipe_type") or "llm_patch_recipe"),
                "target": target,
                "file": path_text,
                "diff": list(
                    difflib.unified_diff(
                        original.splitlines(),
                        patched.splitlines(),
                        fromfile=f"a/{path_text}",
                        tofile=f"b/{path_text}",
                        lineterm="",
                    )
                ),
            }
        ],
    }


def _apply_unified_diff(original: str, diff_lines: list[str]) -> str | None:
    lines = original.splitlines()
    output: list[str] = []
    source_index = 0
    hunks = [line for line in diff_lines if not line.startswith(("--- ", "+++ "))]
    index = 0
    while index < len(hunks):
        header = hunks[index]
        if not header.startswith("@@"):
            index += 1
            continue
        old_start = _old_start(header)
        if old_start is None:
            return None
        start_index = max(old_start - 1, 0)
        if start_index < source_index:
            return None
        output.extend(lines[source_index:start_index])
        source_index = start_index
        index += 1
        while index < len(hunks) and not hunks[index].startswith("@@"):
            line = hunks[index]
            marker, text = line[:1], line[1:]
            if marker == " ":
                if source_index >= len(lines) or lines[source_index] != text:
                    return None
                output.append(text)
                source_index += 1
            elif marker == "-":
                if source_index >= len(lines) or lines[source_index] != text:
                    return None
                source_index += 1
            elif marker == "+":
                output.append(text)
            elif line.startswith("\\"):
                pass
            else:
                return None
            index += 1
    output.extend(lines[source_index:])
    return "\n".join(output) + ("\n" if original.endswith("\n") else "")


def _old_start(header: str) -> int | None:
    try:
        old = header.split(" ", 2)[1]
        return int(old.lstrip("-").split(",", 1)[0])
    except (IndexError, ValueError):
        return None


def _target_symbol(implementation_plan: dict[str, Any]) -> str:
    intent = dict(implementation_plan.get("patch_intent", {}))
    return str(intent.get("target_symbol") or dict(implementation_plan.get("implementation_target") or {}).get("candidate") or "")


def _expected_files(implementation_plan: dict[str, Any]) -> list[str]:
    return [str(item).split(":", 1)[0] for item in implementation_plan.get("expected_files", []) if item]
