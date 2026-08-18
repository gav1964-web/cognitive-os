"""Single-attempt repair proposals for failed sandbox candidate verification."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from .programmer_llm_candidate_contract import build_candidate_contract, normalize_recipe
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
    proposal["sandbox_patch_candidate"] = _sandbox_candidate(proposal, target, evidence)
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
    schema = {
        "action": "propose_patch_recipe",
        "reason": "repair reason grounded in verifier evidence",
        "risk": "residual risk",
        "patch_recipe_hypothesis": {
            "recipe_type": "minimal_semantic_repair",
            "target_symbol": target,
            "edit_format": "replace_function",
            "replacement_source": "complete corrected function with the exact existing signature",
            "summary": "minimal repair",
            "verification_hint": "rerun exact acceptance oracle",
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "Return one JSON object only, without markdown. Propose one minimal repair for the same target using "
                f"every field in this schema: {json.dumps(schema, ensure_ascii=False)}. Prefer edit_format "
                "replace_function and a complete replacement_source with the exact existing signature; do not duplicate "
                "it as diff. Optional fallback diff lines may be an array or one newline-delimited string. Paths must be relative a/ and b/ paths, hunk context "
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
    return {
        "action": action,
        "reason": str(payload.get("reason") or "")[:500],
        "risk": str(payload.get("risk") or "unreviewed_repair_hypothesis")[:500],
        "patch_recipe_hypothesis": normalize_recipe(payload),
    }


def _sandbox_candidate(proposal: dict[str, Any], target: str, evidence: dict[str, Any]) -> dict[str, Any]:
    llm = dict(proposal.get("llm_strategy") or {})
    return build_candidate_contract(
        llm=llm,
        target=target,
        source_excerpt=str(evidence.get("source_excerpt") or ""),
        authority="validated_repair_shape_only_not_applied",
        unavailable_reason="no_repair_patch_recipe_hypothesis",
    )


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
