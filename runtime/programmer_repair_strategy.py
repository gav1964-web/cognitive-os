"""Single-attempt repair proposals for failed sandbox candidate verification."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat


def build_patch_repair_strategy(
    *,
    project_dir: Path,
    implementation_plan: dict[str, Any],
    test_result: dict[str, Any],
) -> dict[str, Any]:
    target = _target(implementation_plan)
    evidence = {
        "target": target,
        "source_excerpt": _source_excerpt(project_dir, target),
        "verification_failure": _failure_summary(test_result),
    }
    proposal = {
        "artifact_type": "PatchRepairProposal",
        "status": "advisory",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "authority": "single_repair_hypothesis_only",
        "target": target,
        "llm_strategy": _llm_repair(evidence),
        "required_verifier_gates": ["sandbox_only", "writable_scope_only", "executable_acceptance_passed"],
    }
    proposal["sandbox_patch_candidate"] = _sandbox_candidate(proposal, target)
    return proposal


def _llm_repair(evidence: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = call_json_chat(_messages(evidence), config=LocalInferenceConfig.from_l45_env())
    except LocalInferenceError as exc:
        return {"status": "unavailable", "reason": str(exc)[:240]}
    normalized = _normalize(payload)
    normalized["status"] = "proposed"
    normalized["authority"] = "single_repair_hypothesis_only"
    return normalized


def _messages(evidence: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Return JSON only. Propose one minimal unified diff repair for the same target. "
                "Do not suggest source-project writes, registry edits, dependency installs, or broad refactors."
            ),
        },
        {"role": "user", "content": str({"repair_evidence": evidence})[:12000]},
    ]


def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "propose_patch_recipe")
    if action != "propose_patch_recipe":
        action = "block_for_review"
    recipe = dict(payload.get("patch_recipe_hypothesis") or payload.get("patch_recipe") or {})
    return {
        "action": action,
        "reason": str(payload.get("reason") or "")[:500],
        "risk": str(payload.get("risk") or "unreviewed_repair_hypothesis")[:500],
        "patch_recipe_hypothesis": {
            "recipe_type": str(recipe.get("recipe_type") or "")[:80],
            "target_symbol": str(recipe.get("target_symbol") or payload.get("target_symbol") or "")[:240],
            "summary": str(recipe.get("summary") or "")[:500],
            "diff": [str(item)[:1000] for item in list(recipe.get("diff") or payload.get("diff") or [])[:80]],
            "verification_hint": str(recipe.get("verification_hint") or "")[:500],
        },
    }


def _sandbox_candidate(proposal: dict[str, Any], target: str) -> dict[str, Any]:
    llm = dict(proposal.get("llm_strategy") or {})
    recipe = dict(llm.get("patch_recipe_hypothesis") or {})
    if llm.get("status") != "proposed" or llm.get("action") != "propose_patch_recipe":
        return {"status": "not_available", "reason": "no_repair_patch_recipe_hypothesis"}
    errors = _candidate_errors(recipe, target)
    return {
        "artifact_type": "SandboxPatchCandidate",
        "status": "blocked_invalid_candidate" if errors else "candidate_ready_for_sandbox_attempt",
        "authority": "validated_repair_shape_only_not_applied",
        "errors": errors,
        "target": target,
        "recipe_type": recipe.get("recipe_type"),
        "diff_line_count": len(list(recipe.get("diff") or [])),
    }


def _candidate_errors(recipe: dict[str, Any], target: str) -> list[str]:
    errors: list[str] = []
    path_text = target.split(":", 1)[0]
    if recipe.get("target_symbol") and recipe.get("target_symbol") != target:
        errors.append("target_symbol_mismatch")
    if not str(recipe.get("recipe_type") or ""):
        errors.append("missing_recipe_type")
    diff = [str(item) for item in list(recipe.get("diff") or [])]
    if not diff:
        errors.append("missing_diff")
    if path_text and diff and not any(path_text in line for line in diff[:10]):
        errors.append("diff_does_not_reference_target_file")
    if any(line.startswith(("--- /", "+++ /")) for line in diff):
        errors.append("absolute_diff_path_forbidden")
    return errors


def _failure_summary(test_result: dict[str, Any]) -> dict[str, Any]:
    failed_commands = [item for item in list(test_result.get("commands") or []) if dict(item).get("status") == "failed"]
    executable = dict(test_result.get("executable_acceptance_result") or {})
    return {
        "status": test_result.get("status"),
        "failed_commands": failed_commands[:2],
        "executable_status": executable.get("status"),
        "executable_stdout_tail": str(dict(executable.get("command") or {}).get("stdout_tail") or "")[-3000:],
    }


def _target(implementation_plan: dict[str, Any]) -> str:
    intent = dict(implementation_plan.get("patch_intent") or {})
    return str(intent.get("target_symbol") or dict(implementation_plan.get("implementation_target") or {}).get("candidate") or "")


def _source_excerpt(project_dir: Path, target: str) -> str:
    path_text, _, symbol = target.partition(":")
    path = (project_dir / path_text).resolve()
    try:
        path.relative_to(project_dir.resolve())
    except ValueError:
        return ""
    if not path.is_file():
        return ""
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source[:4000]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            lines = source.splitlines()
            return "\n".join(lines[node.lineno - 1 : (node.end_lineno or node.lineno)])[:4000]
    return source[:4000]
