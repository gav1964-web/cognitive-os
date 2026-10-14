"""Targeted repair proposals for failed sandbox candidate verification."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from .programmer_change_targets import collect_change_targets
from .programmer_composite_retry import retry_composite_payload
from .bounded_prompt_json import bounded_prompt_json
from .programmer_llm_candidate_contract import build_candidate_contract, normalize_recipe
from .programmer_repair_playbooks import repair_recipe_errors, select_repair_playbooks
from .programmer_source_location import source_location


def build_patch_repair_strategy(
    *,
    project_dir: Path,
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any] | None = None,
    test_result: dict[str, Any],
) -> dict[str, Any]:
    primary = _target(implementation_plan)
    change_targets = collect_change_targets(project_dir, implementation_plan, primary)
    failed_targets = _failed_targets(test_result)
    if failed_targets:
        change_targets = [item for item in change_targets if item.get("target") in failed_targets]
    target = str(change_targets[0].get("target") or primary) if change_targets else primary
    location = source_location(project_dir, target)
    obligations = list(dict((test_plan or {}).get("executable_acceptance") or {}).get("obligations") or [])
    if failed_targets:
        obligations = [item for item in obligations if item.get("target") in failed_targets]
    failure = _failure_summary(test_result)
    evidence = {
        "target": target,
        "source_excerpt": location["excerpt"],
        "source_start_line": location["start_line"],
        "source_context": location["context"],
        "source_context_start_line": location["context_start_line"],
        "verification_failure": failure,
        "repair_playbooks": select_repair_playbooks(test_result),
        "implementation_delta": dict(implementation_plan.get("implementation_delta") or {}),
        "acceptance_obligations": obligations[:8],
        "change_targets": change_targets,
    }
    proposal = {
        "artifact_type": "PatchRepairProposal",
        "status": "advisory",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "authority": "single_repair_hypothesis_only",
        "target": target,
        "repair_playbooks": list(evidence.get("repair_playbooks") or []),
        "llm_strategy": _llm_repair(evidence),
        "required_verifier_gates": ["sandbox_only", "writable_scope_only", "executable_acceptance_passed"],
    }
    proposal["sandbox_patch_candidate"] = _sandbox_candidate(proposal, target, evidence)
    return proposal


def _llm_repair(evidence: dict[str, Any]) -> dict[str, Any]:
    config = LocalInferenceConfig.from_l45_env()
    messages = _messages(evidence)
    try:
        payload = call_json_chat(messages, config=config)
    except LocalInferenceError as exc:
        return {"status": "unavailable", "reason": str(exc)[:240]}
    normalized = _normalize(payload)
    retry_diagnostics: dict[str, Any] = {}
    retry = retry_composite_payload(
        evidence=evidence,
        normalized=normalized,
        initial_payload=payload,
        messages=messages,
        config=config,
        caller=call_json_chat,
        diagnostics=retry_diagnostics,
    )
    if retry is not None:
        normalized = _normalize(retry)
    normalized["schema_retry"] = retry_diagnostics
    normalized["status"] = "proposed"
    normalized["authority"] = "single_repair_hypothesis_only"
    return normalized


def _messages(evidence: dict[str, Any]) -> list[dict[str, str]]:
    target = str(evidence.get("target") or "relative/path.py:function_name")
    playbook_guidance = bounded_prompt_json(evidence.get("repair_playbooks") or [], max_chars=2500)
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
    if len(list(evidence.get("change_targets") or [])) > 1:
        recipe = schema["patch_recipe_hypothesis"]
        recipe["edit_format"] = "replace_functions"
        recipe.pop("replacement_source", None)
        recipe["edits"] = [
            {
                "target_symbol": "one exact target from change_targets",
                "replacement_source": "one complete corrected function with its existing signature",
            }
        ]
    return [
        {
            "role": "system",
            "content": (
                "Return one JSON object only, without markdown. Propose one minimal repair for the same target using "
                f"every field in this schema: {json.dumps(schema, ensure_ascii=False)}. Prefer edit_format "
                "replace_function and a complete replacement_source with the exact existing signature. For multiple "
                "change_targets, return replace_functions with a complete edits item for every target, preserving already "
                "passing behavior. Each replacement_source contains one function and no imports. Do not duplicate it as "
                "diff. Optional fallback diff lines may be an array or one newline-delimited string. Paths must be relative a/ and b/ paths, hunk context "
                "must match source_excerpt exactly, source_start_line must determine the first hunk location, and the "
                "change must satisfy every acceptance_obligation while addressing verifier evidence. Do not suggest "
                "source-project writes, registry edits, installs, or broad refactors. Respect runtime types visible in "
                "source_context. Mentally execute every given input and verify exact equality with each expected output; "
                "preserve cases that already pass and check boolean polarity explicitly. The replacement must differ "
                "from the current source_excerpt and change the expression that explains the observed expected-versus-got "
                "mismatch. Never repeat a replacement that has already failed verification; if no evidence-backed code "
                "change remains, return block_for_review instead of a no-op recipe. Treat repair_playbooks as advisory "
                "counterexample hypotheses: apply their repair_guidance only when it explains the verifier evidence, "
                "and satisfy their required_gates. Selected verifier-derived playbooks: " + playbook_guidance
            ),
        },
        {
            "role": "user",
            "content": bounded_prompt_json({"repair_evidence": evidence}),
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
    changes = [dict(item) for item in list(evidence.get("change_targets") or [])]
    candidate = build_candidate_contract(
        llm=llm,
        target=target,
        source_excerpt=str(evidence.get("source_excerpt") or ""),
        authority="validated_repair_shape_only_not_applied",
        unavailable_reason="no_repair_patch_recipe_hypothesis",
        allowed_targets=[str(item.get("target") or "") for item in changes],
        source_excerpts={str(item.get("target") or ""): str(item.get("source_excerpt") or "") for item in changes},
    )
    policy_errors = repair_recipe_errors(
        dict(llm.get("patch_recipe_hypothesis") or {}), list(evidence.get("repair_playbooks") or [])
    )
    if policy_errors:
        candidate["errors"] = list(dict.fromkeys([*list(candidate.get("errors") or []), *policy_errors]))
        candidate["status"] = "blocked_invalid_candidate"
    return candidate


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


def _failed_targets(test_result: dict[str, Any]) -> set[str]:
    summary = dict(dict(test_result.get("executable_acceptance_result") or {}).get("summary") or {})
    return {
        str(item.get("target") or "")
        for item in list(summary.get("skipped_targets") or [])
        if isinstance(item, dict) and item.get("reason") == "positive_sample_execution_failed"
    } - {""}
