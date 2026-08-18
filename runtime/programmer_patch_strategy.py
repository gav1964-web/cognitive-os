"""Advisory patch strategy proposals for the sandbox Programmer Executor."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from .contract_rebind_request import build_contract_rebind_request
from .dependency_probe_session import build_dependency_probe_session_request
from .executor_solution_patterns import select_solution_patterns
from .programmer_executor_playbooks import select_executor_playbooks
from .programmer_change_targets import collect_change_targets
from .programmer_composite_retry import retry_composite_payload
from .programmer_contract_alignment import contract_alignment
from .bounded_prompt_json import bounded_prompt_json
from .programmer_llm_candidate_contract import build_candidate_contract, normalize_recipe
from .programmer_source_location import source_location

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
    location = source_location(project_dir, target)
    change_targets = collect_change_targets(project_dir, implementation_plan, target)
    evidence = {
        "target": target,
        "source_excerpt": location["excerpt"],
        "source_start_line": location["start_line"],
        "source_context": location["context"],
        "source_context_start_line": location["context_start_line"],
        "contract": dict(dict(implementation_plan.get("contract_binding") or {}).get("input_contract") or {}),
        "acceptance_obligations": list(
            dict(test_plan.get("executable_acceptance") or {}).get("obligations") or []
        )[:8],
        "patch_synthesis": _synthesis_summary(synthesis),
        "acceptance_summary": dict(acceptance_summary or {}),
        "contract_alignment": contract_alignment(
            target,
            test_plan,
            allowed_targets=[str(item.get("target") or "") for item in change_targets],
        ),
        "dependency_boundary_profile": dict(implementation_plan.get("dependency_boundary_profile") or {}),
        "first_slice_reselection_request": dict(implementation_plan.get("first_slice_reselection_request") or {}),
        "implementation_delta": dict(implementation_plan.get("implementation_delta") or {}),
        "change_targets": change_targets,
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
        "implementation_delta": evidence["implementation_delta"],
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
    if isolated_profile := dict(evidence["dependency_boundary_profile"].get("isolated_environment_profile") or {}):
        complete_scope = all(isolated_profile.get(key) for key in ("project_root", "target", "profile_fingerprint"))
        if complete_scope and isolated_profile.get("status") in {"ready_for_probe", "review_required"}:
            proposal["dependency_probe_session_request"] = build_dependency_probe_session_request(isolated_profile)
    proposal["sandbox_patch_candidate"] = _sandbox_candidate(proposal, evidence)
    proposal["recommended_next_step"] = _recommended_next_step(proposal)
    return proposal


def _deterministic_strategy(evidence: dict[str, Any]) -> dict[str, Any]:
    synthesis = dict(evidence.get("patch_synthesis") or {})
    acceptance = dict(evidence.get("acceptance_summary") or {})
    alignment = dict(evidence.get("contract_alignment") or {})
    reasons = dict(acceptance.get("skipped_reason_counts") or {})
    dependency_profile = dict(evidence.get("dependency_boundary_profile") or {})
    isolated_profile = dict(dependency_profile.get("isolated_environment_profile") or {})
    reselection = dict(evidence.get("first_slice_reselection_request") or {})
    delta = dict(evidence.get("implementation_delta") or {})
    if delta.get("status") == "verification_only":
        return _strategy("verify_existing_behavior", "no_evidence_backed_behavior_change", confidence=0.98)
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
            if reselection.get("terminal") is True:
                isolated_status = str(isolated_profile.get("status") or "")
                if isolated_status == "ready_for_probe":
                    return _strategy(
                        "prepare_isolated_dependency_probe",
                        "declared_low_risk_dependency_profile_ready",
                        confidence=0.88,
                    )
                if isolated_status == "review_required":
                    return _strategy(
                        "review_isolated_dependency_profile",
                        "declared_dependency_requires_risk_review",
                        confidence=0.86,
                    )
                if isolated_status.startswith("blocked_"):
                    return _strategy("block_for_review", "isolated_dependency_profile_blocked", confidence=0.9)
                return _strategy(
                    "resolve_dependency_boundary_from_profile",
                    "architect_reselection_exhausted_dependency_resolution_required",
                    confidence=0.86,
                )
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
    config = LocalInferenceConfig.from_l45_env()
    messages = _messages(evidence, deterministic)
    try:
        proposal = call_json_chat(messages, config=config)
    except LocalInferenceError as exc:
        return {"status": "unavailable", "reason": str(exc)[:240]}
    normalized = _normalize_llm_payload(proposal)
    retry_diagnostics: dict[str, Any] = {}
    retry = retry_composite_payload(
        evidence=evidence,
        normalized=normalized,
        initial_payload=proposal,
        messages=messages,
        config=config,
        caller=call_json_chat,
        diagnostics=retry_diagnostics,
    )
    if retry is not None:
        normalized = _normalize_llm_payload(retry)
    normalized["schema_retry"] = retry_diagnostics
    normalized["status"] = "proposed"
    normalized["authority"] = "hypothesis_only"
    return normalized


def _messages(evidence: dict[str, Any], deterministic: dict[str, Any]) -> list[dict[str, str]]:
    schema = {
        "action": "propose_patch_recipe",
        "reason": "short evidence-based reason",
        "risk": "short residual risk",
        "expected_files": ["relative/path.py"],
        "patch_recipe_hypothesis": {
            "recipe_type": "descriptive_recipe_id",
            "target_symbol": "relative/path.py:function_name",
            "edit_format": "replace_function",
            "replacement_source": "def function_name(existing_signature):\n    return corrected_result",
            "summary": "behavior change",
            "verification_hint": "bounded verification",
        },
    }
    if len(list(evidence.get("change_targets") or [])) > 1:
        recipe = schema["patch_recipe_hypothesis"]
        recipe["edit_format"] = "replace_functions"
        recipe.pop("replacement_source", None)
        recipe["edits"] = [
            {
                "target_symbol": "relative/path.py:qualified_function",
                "replacement_source": "complete function with exact existing signature",
                "summary": "bounded behavior change",
            }
        ]
    return [
        {
            "role": "system",
            "content": (
                "Return one JSON object only, without markdown. Propose a sandbox patch strategy, not code execution. "
                "Allowed actions: verify_patch, propose_patch_recipe, request_fixture_profile, "
                "request_contract_rebind, block_for_review. When action is propose_patch_recipe, every field in this "
                f"example schema is required: {json.dumps(schema, ensure_ascii=False)}. Prefer edit_format "
                "replace_function with the complete target function in replacement_source and the exact existing "
                "signature. When change_targets contains multiple entries, use replace_functions and one edits item "
                "per required target; every target must come from change_targets. Do not duplicate structured edits as diff. "
                "Each replacement_source must contain exactly one function and no imports or module-level statements. "
                "This path is AST-validated. An optional fallback unified diff must use "
                "relative a/ and b/ paths, reference only the exact target, and match source_excerpt lines exactly. "
                "Use source_start_line for the first hunk location and satisfy every acceptance_obligation. "
                "Respect types and globals visible in source_context. Mentally execute every given input and confirm "
                "the proposed code equals its expected output before returning. Preserve already-correct cases. "
                "Every edit is an untrusted proposal applied only in an isolated verifier sandbox."
            ),
        },
        {
            "role": "user",
            "content": bounded_prompt_json(
                {"evidence": evidence, "deterministic_strategy": deterministic}
            ),
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
        "patch_recipe_hypothesis": normalize_recipe(payload),
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


def _sandbox_candidate(proposal: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    llm = dict(proposal.get("llm_strategy") or {})
    changes = [dict(item) for item in list(evidence.get("change_targets") or [])]
    return build_candidate_contract(
        llm=llm,
        target=str(evidence.get("target") or ""),
        source_excerpt=str(evidence.get("source_excerpt") or ""),
        authority="validated_shape_only_not_applied",
        unavailable_reason="no_llm_patch_recipe_hypothesis",
        allowed_targets=[str(item.get("target") or "") for item in changes],
        source_excerpts={str(item.get("target") or ""): str(item.get("source_excerpt") or "") for item in changes},
    )


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
