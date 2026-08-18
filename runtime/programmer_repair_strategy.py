"""Single-attempt repair proposals for failed sandbox candidate verification."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from .programmer_source_location import source_location


def build_patch_repair_strategy(
    *,
    project_dir: Path,
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any] | None = None,
    test_result: dict[str, Any],
) -> dict[str, Any]:
    target = _target(implementation_plan)
    location = source_location(project_dir, target)
    evidence = {
        "target": target,
        "source_excerpt": location["excerpt"],
        "source_start_line": location["start_line"],
        "source_context": location["context"],
        "source_context_start_line": location["context_start_line"],
        "verification_failure": _failure_summary(test_result),
        "implementation_delta": dict(implementation_plan.get("implementation_delta") or {}),
        "acceptance_obligations": list(
            dict((test_plan or {}).get("executable_acceptance") or {}).get("obligations") or []
        )[:8],
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
    target = str(evidence.get("target") or "relative/path.py:function_name")
    path_text = target.split(":", 1)[0]
    schema = {
        "action": "propose_patch_recipe",
        "reason": "repair reason grounded in verifier evidence",
        "risk": "residual risk",
        "patch_recipe_hypothesis": {
            "recipe_type": "minimal_semantic_repair",
            "target_symbol": target,
            "summary": "minimal repair",
            "diff": [
                f"--- a/{path_text}",
                f"+++ b/{path_text}",
                "@@ -1,2 +1,2 @@",
                " exact context",
                "-exact old line",
                "+exact new line",
            ],
            "verification_hint": "rerun exact acceptance oracle",
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "Return one JSON object only, without markdown. Propose one minimal unified diff repair for the same "
                f"target using every field in this schema: {json.dumps(schema, ensure_ascii=False)}. Diff lines may "
                "be an array or one newline-delimited string. Paths must be relative a/ and b/ paths, hunk context "
                "must match source_excerpt exactly, source_start_line must determine the first hunk location, and the "
                "change must satisfy every acceptance_obligation while addressing verifier evidence. Do not suggest "
                "source-project writes, registry edits, installs, or broad refactors. Respect runtime types visible in "
                "source_context. Mentally execute every given input and verify exact equality with each expected output; "
                "preserve cases that already pass and check boolean polarity explicitly."
            ),
        },
        {
            "role": "user",
            "content": json.dumps({"repair_evidence": evidence}, ensure_ascii=False, sort_keys=True)[:12000],
        },
    ]


def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "propose_patch_recipe")
    if action != "propose_patch_recipe":
        action = "block_for_review"
    recipe = dict(payload.get("patch_recipe_hypothesis") or payload.get("patch_recipe") or {})
    diff = recipe.get("diff") or payload.get("diff") or []
    diff_lines = diff.splitlines() if isinstance(diff, str) else list(diff)
    return {
        "action": action,
        "reason": str(payload.get("reason") or "")[:500],
        "risk": str(payload.get("risk") or "unreviewed_repair_hypothesis")[:500],
        "patch_recipe_hypothesis": {
            "recipe_type": str(recipe.get("recipe_type") or "")[:80],
            "target_symbol": str(recipe.get("target_symbol") or payload.get("target_symbol") or "")[:240],
            "summary": str(recipe.get("summary") or "")[:500],
            "diff": [str(item)[:1000] for item in diff_lines[:80]],
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
        "executable_summary": dict(executable.get("summary") or {}),
    }


def _target(implementation_plan: dict[str, Any]) -> str:
    intent = dict(implementation_plan.get("patch_intent") or {})
    return str(intent.get("target_symbol") or dict(implementation_plan.get("implementation_target") or {}).get("candidate") or "")
