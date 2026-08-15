"""Advisory patch strategy proposals for the sandbox Programmer Executor."""

from __future__ import annotations

import ast
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from .contract_rebind_request import build_contract_rebind_request
from .executor_solution_patterns import select_solution_patterns
from .programmer_executor_playbooks import select_executor_playbooks


def llm_strategy_enabled() -> bool:
    return os.environ.get("COGNITIVE_OS_EXECUTOR_USE_L45_LLM", "").lower() in {"1", "true", "yes", "on"}


def build_patch_strategy(
    *,
    project_dir: Path,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    synthesis: dict[str, Any],
    acceptance_summary: dict[str, Any] | None = None,
    use_l45_llm: bool = False,
) -> dict[str, Any]:
    target = _target(implementation_plan)
    evidence = {
        "target": target,
        "source_excerpt": _source_excerpt(project_dir, target),
        "contract": dict(dict(implementation_plan.get("contract_binding") or {}).get("input_contract") or {}),
        "patch_synthesis": _synthesis_summary(synthesis),
        "acceptance_summary": dict(acceptance_summary or {}),
        "contract_alignment": _contract_alignment(target, test_plan),
        "dependency_boundary_profile": dict(implementation_plan.get("dependency_boundary_profile") or {}),
        "first_slice_reselection_request": dict(implementation_plan.get("first_slice_reselection_request") or {}),
    }
    quality = _patch_quality(synthesis)
    pattern_context = _pattern_context(acceptance_summary, synthesis, quality)
    deterministic = _deterministic_strategy(evidence)
    playbooks = select_executor_playbooks(acceptance_summary)
    proposal = {
        "artifact_type": "PatchStrategyProposal",
        "status": "advisory",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "authority": "proposal_only_verifier_required",
        "llm_policy": "disabled" if not use_l45_llm else "l45_hypothesis_only",
        "target": target,
        "contract_alignment": evidence["contract_alignment"],
        "dependency_boundary_profile": evidence["dependency_boundary_profile"],
        "first_slice_reselection_request": evidence["first_slice_reselection_request"],
        "deterministic_strategy": deterministic,
        "patch_quality": quality,
        "executor_playbooks": playbooks,
        "solution_patterns": select_solution_patterns(pattern_context),
        "llm_strategy": _llm_strategy(evidence, deterministic) if use_l45_llm else _llm_not_requested(),
        "required_verifier_gates": [
            "sandbox_only",
            "writable_scope_only",
            "executable_acceptance_passed",
            "source_diff_reviewed",
        ],
    }
    if deterministic["action"] == "request_implementation_plan_contract_rebind":
        proposal["contract_rebind_request"] = build_contract_rebind_request(
            target=target,
            reason=str(deterministic["reason"]),
            alignment=dict(evidence["contract_alignment"]),
            technical_spec=technical_spec,
            implementation_plan=implementation_plan,
            test_plan=test_plan,
            acceptance_summary=acceptance_summary,
        )
    proposal["sandbox_patch_candidate"] = _sandbox_candidate(proposal, evidence)
    proposal["recommended_next_step"] = _recommended_next_step(proposal)
    return proposal


def _deterministic_strategy(evidence: dict[str, Any]) -> dict[str, Any]:
    synthesis = dict(evidence.get("patch_synthesis") or {})
    acceptance = dict(evidence.get("acceptance_summary") or {})
    alignment = dict(evidence.get("contract_alignment") or {})
    reasons = dict(acceptance.get("skipped_reason_counts") or {})
    dependency_profile = dict(evidence.get("dependency_boundary_profile") or {})
    reselection = dict(evidence.get("first_slice_reselection_request") or {})
    if alignment.get("status") == "target_drift":
        reason = (
            "test_plan_target_drift"
            if alignment.get("reason") == "obligation_target_mismatch"
            else "test_plan_acceptance_scope_drift"
        )
        return _strategy("request_implementation_plan_contract_rebind", reason, confidence=0.81)
    if acceptance.get("signal_strength") == "executable_callable":
        return _strategy("verify_patch", "callable_acceptance_available", confidence=0.78)
    if reasons.get("positive_sample_execution_failed"):
        return _strategy("request_fixture_or_contract_refinement", "positive_sample_not_materializable", confidence=0.72)
    if reasons.get("positive_signature_mismatch"):
        return _strategy("request_implementation_plan_contract_rebind", "signature_contract_mismatch", confidence=0.74)
    if reasons.get("method_target_needs_instance_fixture"):
        return _strategy("request_fixture_or_contract_refinement", "method_instance_fixture_missing", confidence=0.72)
    if reasons.get("nested_function_requires_closure"):
        return _strategy("request_implementation_plan_contract_rebind", "nested_closure_target", confidence=0.82)
    if reasons.get("import_failed_missing_module") or reasons.get("import_failed_import_error"):
        if reselection.get("status") == "required":
            return _strategy("return_to_architect_for_first_slice_reselection", "no_environment_ready_first_slice", confidence=0.84)
        if dependency_profile.get("status") == "resolution_required":
            return _strategy("resolve_dependency_boundary_from_profile", "dependency_profile_requires_resolution", confidence=0.78)
        return _strategy("request_dependency_boundary_profile", "optional_dependency_boundary", confidence=0.68)
    if reasons.get("import_failed_runtime_error"):
        return _strategy("block_for_review", "import_time_runtime_boundary", confidence=0.66)
    if synthesis.get("status") == "prepared":
        return _strategy("verify_patch", str(synthesis.get("reason") or "deterministic_patch_prepared"), confidence=0.64)
    if synthesis.get("status") == "skipped":
        return _strategy("ask_l45_for_patch_recipe_hypothesis", "no_deterministic_patch_recipe", confidence=0.55)
    return _strategy("block_for_review", str(synthesis.get("reason") or "unknown_executor_boundary"), confidence=0.5)


def _strategy(action: str, reason: str, *, confidence: float) -> dict[str, Any]:
    return {
        "action": action,
        "reason": reason,
        "confidence": confidence,
        "allowed_to_apply_source": False,
        "requires_human_or_verifier_acceptance": True,
    }


def _llm_strategy(evidence: dict[str, Any], deterministic: dict[str, Any]) -> dict[str, Any]:
    try:
        proposal = call_json_chat(_messages(evidence, deterministic), config=LocalInferenceConfig.from_l45_env())
    except LocalInferenceError as exc:
        return {"status": "unavailable", "reason": str(exc)[:240]}
    normalized = _normalize_llm_payload(proposal)
    normalized["status"] = "proposed"
    normalized["authority"] = "hypothesis_only"
    return normalized


def _messages(evidence: dict[str, Any], deterministic: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Return JSON only. Propose a sandbox patch strategy, not code execution. "
                "Allowed actions: verify_patch, propose_patch_recipe, request_fixture_profile, "
                "request_contract_rebind, block_for_review."
            ),
        },
        {
            "role": "user",
            "content": str({"evidence": evidence, "deterministic_strategy": deterministic})[:12000],
        },
    ]


def _normalize_llm_payload(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "block_for_review")
    allowed = {"verify_patch", "propose_patch_recipe", "request_fixture_profile", "request_contract_rebind", "block_for_review"}
    if action not in allowed:
        action = "block_for_review"
    return {
        "action": action,
        "reason": str(payload.get("reason") or "")[:500],
        "risk": str(payload.get("risk") or "unreviewed_llm_hypothesis")[:500],
        "expected_files": [str(item) for item in list(payload.get("expected_files") or [])[:5]],
        "patch_recipe_hypothesis": _patch_recipe_hypothesis(payload),
    }


def _recommended_next_step(proposal: dict[str, Any]) -> str:
    llm = dict(proposal.get("llm_strategy") or {})
    candidate = dict(proposal.get("sandbox_patch_candidate") or {})
    if candidate.get("status") == "candidate_ready_for_sandbox_attempt":
        return "run_reviewed_sandbox_patch_candidate"
    if llm.get("status") == "proposed" and llm.get("action") == "propose_patch_recipe":
        return "review_llm_patch_recipe_hypothesis_before_sandbox_attempt"
    return str(dict(proposal.get("deterministic_strategy") or {}).get("action") or "block_for_review")


def _llm_not_requested() -> dict[str, str]:
    return {"status": "not_requested", "reason": "COGNITIVE_OS_EXECUTOR_USE_L45_LLM is not enabled"}


def _patch_recipe_hypothesis(payload: dict[str, Any]) -> dict[str, Any]:
    recipe = payload.get("patch_recipe_hypothesis") or payload.get("patch_recipe") or {}
    recipe = recipe if isinstance(recipe, dict) else {}
    return {
        "recipe_type": str(recipe.get("recipe_type") or "")[:80],
        "target_symbol": str(recipe.get("target_symbol") or payload.get("target_symbol") or "")[:240],
        "summary": str(recipe.get("summary") or "")[:500],
        "diff": [str(item)[:1000] for item in list(recipe.get("diff") or payload.get("diff") or [])[:80]],
        "verification_hint": str(recipe.get("verification_hint") or "")[:500],
    }


def _sandbox_candidate(proposal: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    llm = dict(proposal.get("llm_strategy") or {})
    recipe = dict(llm.get("patch_recipe_hypothesis") or {})
    if llm.get("status") != "proposed" or llm.get("action") != "propose_patch_recipe":
        return {"status": "not_available", "reason": "no_llm_patch_recipe_hypothesis"}
    errors = _candidate_errors(recipe, evidence)
    return {
        "artifact_type": "SandboxPatchCandidate",
        "status": "blocked_invalid_candidate" if errors else "candidate_ready_for_sandbox_attempt",
        "authority": "validated_shape_only_not_applied",
        "errors": errors,
        "target": str(evidence.get("target") or ""),
        "recipe_type": recipe.get("recipe_type"),
        "diff_line_count": len(list(recipe.get("diff") or [])),
    }


def _candidate_errors(recipe: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    target = str(evidence.get("target") or "")
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


def _synthesis_summary(synthesis: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": synthesis.get("status"),
        "reason": synthesis.get("reason"),
        "patch_count": len(list(synthesis.get("patches") or [])),
    }


def _pattern_context(
    acceptance_summary: dict[str, Any] | None,
    synthesis: dict[str, Any],
    quality: dict[str, Any],
) -> dict[str, Any]:
    acceptance = dict(acceptance_summary or {})
    return {
        "acceptance_signal": str(acceptance.get("signal_strength") or ""),
        "patch_synthesis": str(synthesis.get("status") or ""),
        "patch_reason": str(synthesis.get("reason") or ""),
        "patch_quality_level": str(quality.get("level") or ""),
        "patch_quality_review_required": bool(quality.get("review_required")),
    }


def _contract_alignment(target: str, test_plan: dict[str, Any]) -> dict[str, Any]:
    obligations = list(dict(test_plan.get("executable_acceptance") or {}).get("obligations") or [])
    target_mismatches = sorted(
        {
            str(item.get("target") or "")
            for item in obligations
            if isinstance(item, dict) and item.get("target") and str(item.get("target")) != target
        }
    )
    criterion_refs = [
        (str(item.get("source_criterion") or ""), ref)
        for item in obligations
        if isinstance(item, dict)
        for ref in set(re.findall(r"[\w./-]+\.py:[A-Za-z_]\w*", str(item.get("source_criterion") or "")))
    ]
    refs = sorted({ref for _, ref in criterion_refs})
    mismatches = [ref for ref in refs if target and ref != target]
    direct = sorted(
        {
            ref
            for criterion, ref in criterion_refs
            if ref != target and "selected extraction_contract" in criterion.lower()
        }
    )
    counts = {ref: sum(1 for _, candidate in criterion_refs if candidate == ref) for ref in mismatches}
    repeated = sorted(ref for ref, count in counts.items() if count >= 2)
    candidates = list(dict.fromkeys(target_mismatches + direct + repeated))[:5]
    if target_mismatches or direct or repeated:
        reason = "obligation_target_mismatch" if target_mismatches else "authoritative_source_criterion_mismatch"
        return {
            "status": "target_drift",
            "reason": reason,
            "target": target,
            "mismatched_targets": target_mismatches[:5],
            "source_refs": mismatches[:5],
            "candidate_targets": candidates,
        }
    return {
        "status": "aligned",
        "target": target,
        "mismatched_targets": [],
        "source_refs": mismatches[:5],
        "candidate_targets": [],
    }


def _patch_quality(synthesis: dict[str, Any]) -> dict[str, Any]:
    if synthesis.get("status") == "skipped":
        return {"level": "verified_no_patch", "review_required": False, "evidence_sources": []}
    if synthesis.get("status") == "blocked":
        return {"level": "blocked_handoff", "review_required": False, "evidence_sources": []}
    patches = [dict(item) for item in list(synthesis.get("patches") or []) if isinstance(item, dict)]
    evidence = [dict(item.get("guard_evidence") or {}) for item in patches]
    evidence.extend(dict(item.get("return_evidence") or {}) for item in patches)
    evidence.extend(dict(item.get("transform_evidence") or {}) for item in patches)
    sources = sorted({str(item.get("source") or "") for item in evidence if item.get("source")})
    if "contract_missing_input_case" in sources:
        return {"level": "contract_backed_guard", "review_required": False, "evidence_sources": sources}
    if "contract_return_literal_case" in sources:
        return {"level": "contract_backed_return_literal", "review_required": False, "evidence_sources": sources}
    if "contract_return_literal_notimplemented_case" in sources:
        return {"level": "contract_backed_notimplemented_return", "review_required": False, "evidence_sources": sources}
    if "contract_identity_transform_case" in sources or "contract_string_transform_case" in sources:
        return {"level": "contract_backed_identity_transform", "review_required": False, "evidence_sources": sources}
    if "signature_required_parameters" in sources:
        return {"level": "signature_fallback_guard", "review_required": True, "evidence_sources": sources}
    return {"level": "unclassified_patch", "review_required": True, "evidence_sources": sources}


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
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return path.read_text(encoding="utf-8", errors="replace")[:4000]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            lines = path.read_text(encoding="utf-8").splitlines()
            return "\n".join(lines[node.lineno - 1 : (node.end_lineno or node.lineno)])[:4000]
    return ""
