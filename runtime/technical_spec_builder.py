"""Generic TechnicalSpec artifact builder."""

from __future__ import annotations

import ast
import builtins
import re
from typing import Any

from .role_spec_writer_ranking import (
    candidate_level_bonus as _candidate_level_bonus,
    name_and_contract_score as _name_and_contract_score,
    operational_boundary_score as _operational_boundary_score,
)
from .role_skill_common import now_iso
from .target_quality import semantic_target_quality_report


_BUILTIN_NAMES = set(dir(builtins))
_ALLOWED_EXTERNAL_SNIPPET_NAMES = {
    "Any",
    "Dict",
    "List",
    "Optional",
    "Path",
    "model",
    "np",
    "pd",
    "self",
    "time",
    "tokenizer",
    "torch",
}
_HIGH_CONFIDENCE_UNRESOLVED_SETS = (
    frozenset({"pipe", "output"}),
)


def build_technical_spec(
    *,
    architecture_decision: dict[str, Any],
    role_id: str = "spec_writer",
    next_role_id: str = "implementer",
) -> dict[str, Any]:
    brief = dict(architecture_decision.get("spec_writer_brief", {}))
    chosen = dict(architecture_decision.get("chosen_option", {}))
    traceability = list(architecture_decision.get("traceability", []))
    source_context = dict(architecture_decision.get("source_context", {}))
    evidence = _source_evidence(brief, source_context)
    work_plan_contract = _work_plan_contract(brief, architecture_decision)
    acceptance = _acceptance_criteria(brief, traceability)
    preferred_targets = [] if work_plan_contract.get("source") == "TechnicalSpec.fallback_from_spec_writer_brief" else list(work_plan_contract.get("targets", []))
    extraction_contract = _extraction_contract(evidence, preferred_targets=preferred_targets)
    acceptance = _ensure_candidate_acceptance(acceptance, extraction_contract)
    return {
        "artifact_type": "TechnicalSpec",
        "role": role_id,
        "status": "ok",
        "created_at": now_iso(),
        "source_artifact": {
            "type": architecture_decision.get("artifact_type"),
            "role": architecture_decision.get("role"),
            "goal": architecture_decision.get("goal"),
        },
        "scope": brief.get("scope", []),
        "chosen_architecture_option": chosen.get("id"),
        "requirements": _requirements_from_brief(brief, traceability),
        "source_evidence": evidence,
        "extraction_contract": extraction_contract,
        "work_plan_contract": work_plan_contract,
        "interface_contracts": _interface_contracts(brief, evidence, extraction_contract),
        "data_lifecycle": _data_lifecycle(brief, architecture_decision),
        "state_and_replay_policy": _state_and_replay_policy(brief, architecture_decision),
        "error_model": _error_model(brief, architecture_decision, extraction_contract),
        "acceptance_criteria": acceptance,
        "verification_strategy": _verification_strategy(acceptance, extraction_contract, work_plan_contract),
        "constraints": brief.get("constraints", []),
        "non_goals": architecture_decision.get("non_goals", []),
        "open_questions": architecture_decision.get("open_questions", []),
        "traceability_table": _spec_traceability(traceability, acceptance),
        "implementation_handoff": {
            "recommended_role": next_role_id,
            "expected_output": "ImplementationPlan",
            "patch_scope": _handoff_patch_scope(brief, work_plan_contract),
        },
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
    }


def _requirements_from_brief(brief: dict[str, Any], traceability: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, scope_item in enumerate(brief.get("scope", []) or []):
        rows.append(
            {
                "id": f"REQ-{index + 1:03d}",
                "statement": str(scope_item),
                "source": "spec_writer_brief.scope",
                "priority": "MUST" if index == 0 else "SHOULD",
            }
        )
    offset = len(rows)
    for index, row in enumerate(traceability[:6]):
        source = row.get("source")
        rows.append(
            {
                "id": f"REQ-{offset + index + 1:03d}",
                "statement": _requirement_statement(str(row.get("requirement")), source),
                "source": source,
                "target": row.get("target"),
                "priority": "MUST",
            }
        )
    first_slice = dict(brief.get("first_slice") or {})
    for index, step in enumerate(list(first_slice.get("steps", []))[:8], start=1):
        rows.append(
            {
                "id": f"REQ-{len(rows) + 1:03d}",
                "statement": f"First-slice step {index} must be represented as a bounded implementation obligation: {step}",
                "source": first_slice.get("source") or "ProjectArchitectureSynthesis.recommended_first_slice",
                "target": _step_target(first_slice, index),
                "priority": "MUST",
            }
        )
    return rows


def _acceptance_criteria(brief: dict[str, Any], traceability: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets = _acceptance_targets(brief, traceability)
    criteria = []
    for index, target in enumerate(targets[:40]):
        criteria.append(
            {
                "id": f"AC-{index + 1:03d}",
                "criterion": target["criterion"],
                "verification": "pytest or explicit review checklist",
                "source": target.get("source"),
            }
        )
    first_slice = dict(brief.get("first_slice") or {})
    for index, step in enumerate(list(first_slice.get("steps", []))[:8], start=1):
        criteria.append(
            {
                "id": f"AC-{len(criteria) + 1:03d}",
                "criterion": f"First-slice `{first_slice.get('name')}` step {index} is implemented or explicitly blocked with evidence: {step}",
                "verification": "contract test, negative test, or explicit implementation checklist tied to the target source",
                "source": _step_target(first_slice, index) or first_slice.get("source"),
            }
        )
    criteria.append(
        {
            "id": f"AC-{len(criteria) + 1:03d}",
            "criterion": "Implementation does not mutate Capability Registry outside explicit Foundry promote.",
            "verification": "acceptance artifact and registry diff check",
        }
    )
    return criteria


def _ensure_candidate_acceptance(criteria: list[dict[str, Any]], extraction_contract: dict[str, Any]) -> list[dict[str, Any]]:
    candidate = str(extraction_contract.get("candidate") or "")
    if not candidate:
        return _renumber_acceptance(criteria)
    if any(_candidate_acceptance_is_explicit(row, candidate) for row in criteria if isinstance(row, dict)):
        return _renumber_acceptance(criteria)
    rows = list(criteria)
    rows.insert(
        0,
        {
            "id": "AC-001",
            "criterion": f"`{candidate}` satisfies the selected extraction_contract input/output shape and failure policy.",
            "verification": "contract test or explicit review checklist tied to the selected source target",
            "source": candidate,
        },
    )
    return _renumber_acceptance(rows)


def _candidate_acceptance_is_explicit(row: dict[str, Any], candidate: str) -> bool:
    if str(row.get("source") or "") != candidate:
        return False
    criterion = str(row.get("criterion") or "").lower()
    return "selected extraction_contract" in criterion or "input/output shape" in criterion


def _renumber_acceptance(criteria: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, row in enumerate(criteria, start=1):
        item = dict(row)
        item["id"] = f"AC-{index:03d}"
        rows.append(item)
    return rows


def _work_plan_contract(brief: dict[str, Any], architecture_decision: dict[str, Any]) -> dict[str, Any]:
    first_slice = dict(brief.get("first_slice") or architecture_decision.get("first_slice_contract") or {})
    if not first_slice:
        fallback_targets = [
            _normalize_source_ref(str(item))
            for item in list(brief.get("files_or_symbols", []))
            if _implementation_source(str(item))
        ]
        if fallback_targets:
            return _fallback_work_plan_contract(fallback_targets)
        return {
            "status": "blocked_no_first_slice",
            "source": "ArchitectureDecisionRecord.first_slice_contract",
            "name": None,
            "goal": "No source-backed first slice was provided by Architect.",
            "targets": [],
            "obligations": [],
            "blocked_by": ["missing_first_slice_contract"],
        }
    obligations = []
    steps = list(first_slice.get("steps", []))
    targets = [_normalize_source_ref(str(item)) for item in list(first_slice.get("targets", [])) if item]
    if not targets:
        return {
            "status": "blocked_no_first_slice",
            "source": first_slice.get("source") or "ArchitectureDecisionRecord.first_slice_contract",
            "name": first_slice.get("name"),
            "goal": "Architect did not provide a safe source-backed target for this first slice.",
            "targets": [],
            "knowledge_rule": first_slice.get("knowledge_rule"),
            "obligations": [],
            "blocked_by": ["no_safe_source_specific_candidate"],
        }
    for index, step in enumerate(steps[:12], start=1):
        obligations.append(
            {
                "id": f"WPC-{index:03d}",
                "step": str(step),
                "target": _step_target(first_slice, index),
                "input": "source-backed evidence, current behavior, and declared capability boundary",
                "output": "bounded implementation obligation with acceptance and rollback evidence",
                "verification": "must be linked to at least one acceptance criterion before Implementer handoff",
            }
        )
    return {
        "status": "ready" if obligations else "needs_manual_step_definition",
        "source": first_slice.get("source") or "ArchitectureDecisionRecord.first_slice_contract",
        "name": first_slice.get("name"),
        "goal": first_slice.get("goal"),
        "targets": targets[:8],
        "knowledge_rule": first_slice.get("knowledge_rule"),
        "obligations": obligations,
    }


def _fallback_work_plan_contract(targets: list[str]) -> dict[str, Any]:
    targets = _dedupe([_normalize_source_ref(str(item)) for item in targets if item])
    primary = targets[0]
    steps = [
        f"Define explicit input/output contract for {primary}.",
        f"Record side-effect and retry policy for {primary}.",
        f"Attach source-linked acceptance and negative-test expectations for {primary}.",
    ]
    return {
        "status": "ready",
        "source": "TechnicalSpec.fallback_from_spec_writer_brief",
        "name": "extraction_contract_slice",
        "goal": f"Prepare a bounded implementation handoff for `{primary}` from source-backed SpecWriter evidence.",
        "targets": targets[:24],
        "knowledge_rule": None,
        "obligations": [
            {
                "id": f"WPC-{index:03d}",
                "step": step,
                "target": primary,
                "input": "source-backed evidence, current behavior, and declared capability boundary",
                "output": "bounded implementation obligation with acceptance and rollback evidence",
                "verification": "must be linked to at least one acceptance criterion before Implementer handoff",
            }
            for index, step in enumerate(steps, start=1)
        ],
    }


def _source_evidence(brief: dict[str, Any], source_context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    first_slice = dict(brief.get("first_slice") or {})
    contract_targets = [
        target.get("source")
        for target in list(brief.get("contract_targets", []) or [])
        if isinstance(target, dict) and target.get("source")
    ]
    sources = _dedupe(
        [
            *[_normalize_source_ref(str(source)) for source in list(brief.get("files_or_symbols", []) or []) if source],
            *[_normalize_source_ref(str(source)) for source in list(first_slice.get("targets", []) or []) if source],
            *[_normalize_source_ref(str(source)) for source in contract_targets if source],
        ]
    )
    for source in sources:
        if not _implementation_source(str(source)):
            continue
        source = _normalize_source_ref(str(source))
        context = dict(source_context.get(str(source), {}))
        snippet = dict(context.get("snippet", {}))
        signature = dict(context.get("signature", {}))
        rows.append(
            {
                "source": str(source),
                "kind": context.get("kind") or "unknown",
                "snippet": snippet.get("text"),
                "signature": signature,
                "callers": context.get("callers", []),
                "callees": context.get("callees", []),
                "side_effects": context.get("side_effects", []),
                "claims": context.get("claims", []),
            }
        )
    return rows


def _implementation_source(source: str) -> bool:
    lowered = source.lower()
    if _context_only_implementation_source(lowered):
        return False
    if ".py:" in lowered:
        return True
    if lowered.startswith("[") and " " in lowered:
        return True
    return False


def _context_only_implementation_source(lowered: str) -> bool:
    normalized = "/" + lowered.replace("\\", "/").lstrip("/")
    return any(
        token in normalized
        for token in (
            "/.github/",
            "/bench/",
            "/benchmarks/",
            "/doc/",
            "/docs/",
            "/examples/",
            "/scripts/",
            "/tasks/",
            "/test/",
            "/tests/",
            "/testing/",
            "/tools/",
            "/__pycache__/",
        )
    )


def _normalize_source_ref(source: str) -> str:
    return re.sub(r"\s*\(\d+\s+loc\)\s*$", "", str(source or "").strip(), flags=re.IGNORECASE)


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    rows = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        rows.append(value)
    return rows


def _extraction_contract(evidence: list[dict[str, Any]], *, preferred_targets: list[Any] | None = None) -> dict[str, Any]:
    ranked = _semantic_rerank_candidates(_rank_extraction_candidates(evidence), evidence)
    ranked = _promote_preferred_first_slice_target(ranked, preferred_targets or [])
    if not ranked:
        return {
            "status": "blocked_no_safe_candidate",
            "candidate": None,
            "candidate_score": 0,
            "selection_reason": "no source-specific evidence available for a bounded extraction contract",
            "ranked_candidates": [],
            "semantic_quality": semantic_target_quality_report(""),
            "input_contract": {},
            "output_contract": {},
            "side_effects": {"declared": [], "requires_process_boundary": False},
            "evidence_source": None,
            "blocked_by": ["no_safe_source_specific_candidate"],
        }
    candidate = dict(ranked[0].get("evidence", {})) if ranked else {}
    args = list(dict(candidate.get("signature", {})).get("args", []))
    source = str(candidate.get("source") or "")
    domain_contract = _domain_extraction_contract(source)
    input_contract = _input_contract_from_candidate(candidate)
    output_contract = _output_contract_from_candidate(candidate)
    contract = {
        "candidate": candidate.get("source"),
        "candidate_score": ranked[0]["score"] if ranked else 0,
        "selection_reason": "; ".join(ranked[0]["reasons"]) if ranked else "no source evidence available",
        "ranked_candidates": [
            {
                "source": item.get("source"),
                "kind": item.get("kind"),
                "score": item.get("score"),
                "reasons": item.get("reasons", []),
                "side_effects": item.get("side_effects", []),
            }
            for item in ranked[:32]
        ],
        "input_contract": domain_contract.get("input_contract") or input_contract,
        "output_contract": domain_contract.get("output_contract") or output_contract,
        "side_effects": {
            "declared": candidate.get("side_effects", []),
            "requires_process_boundary": bool(candidate.get("side_effects")),
            **dict(domain_contract.get("side_effect_policy") or {}),
        },
        "evidence_source": candidate.get("source"),
    }
    if domain_contract.get("contract_family"):
        contract["contract_family"] = domain_contract["contract_family"]
        contract["validation_gates"] = domain_contract.get("validation_gates", [])
        contract["failure_modes"] = domain_contract.get("failure_modes", [])
    contract["semantic_quality"] = semantic_target_quality_report(
        str(contract.get("candidate") or ""),
        ranked_candidates=[str(row.get("source")) for row in contract["ranked_candidates"] if isinstance(row, dict)],
        source_evidence=[str(row.get("source")) for row in evidence if row.get("source")],
        selection_reason=str(contract.get("selection_reason") or ""),
    )
    return contract


def _domain_extraction_contract(source: str) -> dict[str, Any]:
    lowered = source.replace("\\", "/").lower()
    if lowered.endswith(":generate_response") and any(token in lowered for token in ("x31.py:", "inference", "submission", "predict")):
        return {
            "contract_family": "ml_generation_boundary",
            "input_contract": {
                "prompt_text": "PromptText(non_empty_string, source_row_id?)",
                "generation_config": "GenerationConfig(max_new_tokens, temperature, top_p, device_policy)",
                "model_adapter": "ModelAdapter(tokenize, generate, decode; fakeable in tests)",
            },
            "output_contract": {
                "generated_answer": "GeneratedAnswer(text, raw_text_ref?, token_count?, model_id, row_id?)",
                "failure_packet": "ModelInferenceFailure(kind, retryable, evidence_ref)",
            },
            "side_effect_policy": {
                "requires_process_boundary": True,
                "model_policy": "large model/tokenizer loading is injected or fixture-backed in contract tests",
                "secret_policy": "provider/model tokens are environment references, never source literals",
            },
            "validation_gates": [
                "prompt text is non-empty and tied to a row id when available",
                "model adapter can be replaced by a fake fixture for tests",
                "generation failure returns ModelInferenceFailure instead of crashing row processing",
                "hardcoded access tokens are removed before implementation promotion",
                "submission schema is verified without live HuggingFace/GPU dependency",
            ],
            "failure_modes": [
                "missing_model_dependency",
                "missing_or_invalid_token",
                "gpu_or_memory_unavailable",
                "empty_generation",
                "decode_failure",
            ],
        }
    if "core/consensus/engine.py:run_consensus" in lowered:
        return {
            "contract_family": "agent_consensus_orchestration_boundary",
            "input_contract": {
                "consensus_input": "ConsensusInput(task_envelope, participant_agents, quorum_policy, timeout_seconds, run_id)",
                "agent_responses": "list[AgentResponse(status, payload?, error?, latency_ms, agent_id)]",
            },
            "output_contract": {
                "consensus_result": "ConsensusResult(status, selected_payload?, scores, failures, quorum_met, run_id)",
                "failure_packet": "AgentFailurePacket(kind, agent_id?, retryable, evidence_ref)",
            },
            "side_effect_policy": {
                "requires_process_boundary": True,
                "network_policy": "agent calls must pass through timeout/retry/quarantine adapters",
                "replay_policy": "run_id and task ids are persisted before dispatch",
            },
            "validation_gates": [
                "consensus input validates participant list and quorum policy before dispatch",
                "each agent response is normalized before aggregation",
                "timeouts and malformed responses become AgentFailurePacket records",
                "quorum failure is explicit and does not masquerade as successful consensus",
                "resume uses persisted run_id/task ids instead of repeating completed agent calls blindly",
            ],
            "failure_modes": [
                "agent_timeout",
                "malformed_a2a_response",
                "quorum_not_met",
                "conflicting_agent_outputs",
                "partial_resume_requires_replay_guard",
            ],
        }
    if not lowered.endswith(":send_to_model"):
        return {}
    if "auto_dev_agent.py:" not in lowered:
        return {}
    return {
        "contract_family": "llm_repair_hypothesis_boundary",
        "input_contract": {
            "failure_evidence": "FailureEvidence(error_text, build_log?, run_log?, attempt_id, code_version)",
            "workspace_snapshot": "WorkspaceSnapshot(read_only_files, allowed_relative_paths, template_root)",
            "repair_policy": "RepairPolicy(max_attempts, allowed_files, provider_config_ref, timeout_seconds)",
        },
        "output_contract": {
            "model_patch_proposal": "ModelPatchProposal(files: list[PatchFile], rationale, confidence?, raw_response_ref)",
            "validation_result": "PatchValidationResult(valid, violations, diff_preview_ref, normalized_payload_ref)",
            "attempt_outcome": "AttemptOutcome(status in accepted|rejected|needs_review, next_action)",
        },
        "side_effect_policy": {
            "requires_validation_gate": True,
            "writes_allowed_after": "PatchValidationResult.valid == true and diff preview is recorded",
            "network_policy": "LLM call is allowed only through configured provider adapter with captured request id",
        },
        "validation_gates": [
            "raw LLM response is persisted as evidence before parsing",
            "JSON payload validates against ModelPatchProposal schema",
            "every patch file is inside allowed relative paths",
            "no file write occurs before validation_result.valid is true",
            "Docker build/run verification records stdout, stderr, exit code, timeout, and attempt id",
        ],
        "failure_modes": [
            "invalid_model_json",
            "path_traversal_or_forbidden_file",
            "missing_required_patch_file",
            "provider_timeout_or_rate_limit",
            "docker_build_failed",
            "docker_run_failed",
        ],
    }


def _promote_preferred_first_slice_target(ranked: list[dict[str, Any]], preferred_targets: list[Any]) -> list[dict[str, Any]]:
    preferred = [_normalize_source_ref(str(item)) for item in preferred_targets if item]
    if not ranked or not preferred:
        return ranked
    by_source = {str(item.get("source") or ""): item for item in ranked}
    best_score = int(ranked[0].get("score") or 0)
    for target in preferred:
        if target not in by_source:
            continue
        if not _first_slice_target_can_override(by_source[target], best_score=best_score):
            continue
        selected = dict(by_source[target])
        selected["reasons"] = [
            *list(selected.get("reasons", [])),
            "ProjectArchitectureSynthesis first-slice target takes precedence over convenience-only pure transforms",
        ]
        selected["score"] = int(selected.get("score") or 0) + 80
        return [selected, *[item for item in ranked if item is not by_source[target]]]
    return ranked


def _first_slice_target_can_override(item: dict[str, Any], *, best_score: int) -> bool:
    source = str(item.get("source") or "").lower()
    if _domain_extraction_contract(str(item.get("source") or "")).get("contract_family"):
        return True
    if int(item.get("score") or 0) < best_score - 30:
        return False
    if _ranked_item_has_weak_io(item):
        return False
    if int(item.get("score") or 0) >= best_score:
        return True
    side_effects = {str(effect).lower() for effect in list(item.get("side_effects", []))}
    runtime_markers = (
        "send_to_model",
        "llm",
        "model",
        "provider",
        "consensus",
        "orchestrator",
        "group_manager",
        "a2a_protocol",
        "agent",
        "pipeline",
        "docker_",
        "subprocess",
        "request",
        "http",
        "network",
        "write_files",
        "copy_template",
    )
    if any(marker in source for marker in runtime_markers):
        return True
    return bool(side_effects & {"network", "subprocess", "filesystem", "filesystem_write", "database"})


def _ranked_item_has_weak_io(item: dict[str, Any]) -> bool:
    evidence = dict(item.get("evidence", {}))
    signature = dict(evidence.get("signature", {}))
    args = list(signature.get("args", []) or [])
    returns = str(signature.get("returns") or "").strip()
    has_typed_input = any(isinstance(arg, dict) and str(arg.get("annotation") or "").strip() for arg in args)
    return not has_typed_input or not returns


def _interface_contracts(
    brief: dict[str, Any],
    evidence: list[dict[str, Any]],
    extraction_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    if extraction_contract.get("status") == "blocked_no_safe_candidate":
        return []
    rows: list[dict[str, Any]] = []
    contract_targets = brief.get("contract_targets", [])
    for target in contract_targets if isinstance(contract_targets, list) else []:
        if not isinstance(target, dict) or not target.get("source"):
            continue
        source = _normalize_source_ref(str(target.get("source")))
        matching = next((row for row in evidence if row.get("source") == source), {})
        signature = dict(matching.get("signature", {}))
        rows.append(
            {
                "source": source,
                "input_contract": _input_contract_from_signature(signature, target.get("input_hint")),
                "output_contract": _output_contract_from_signature(signature, target.get("output_hint")),
                "side_effect_policy": _side_effect_policy(list(matching.get("side_effects", []) or target.get("side_effects", []) or [])),
            }
        )
    candidate = str(extraction_contract.get("candidate") or "")
    if candidate and not any(row.get("source") == candidate for row in rows):
        rows.append(
            {
                "source": candidate,
                "input_contract": dict(extraction_contract.get("input_contract", {})),
                "output_contract": dict(extraction_contract.get("output_contract", {})),
                "side_effect_policy": _side_effect_policy(list(dict(extraction_contract.get("side_effects", {})).get("declared", []))),
            }
        )
    rows = _dedupe_interface_contracts(_candidate_first(rows, candidate))
    if rows:
        return rows[:16]
    if not candidate:
        return []
    return [
        {
            "source": candidate,
            "input_contract": dict(extraction_contract.get("input_contract", {})),
            "output_contract": dict(extraction_contract.get("output_contract", {})),
            "side_effect_policy": _side_effect_policy(list(dict(extraction_contract.get("side_effects", {})).get("declared", []))),
        }
    ]


def _dedupe_interface_contracts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for row in rows:
        source = str(row.get("source") or "")
        if not source or source in seen:
            continue
        seen.add(source)
        result.append(row)
    return result


def _candidate_first(rows: list[dict[str, Any]], candidate: str) -> list[dict[str, Any]]:
    if not candidate:
        return rows
    return [row for row in rows if row.get("source") == candidate] + [
        row for row in rows if row.get("source") != candidate
    ]


def _input_contract_from_signature(signature: dict[str, Any], fallback: object) -> dict[str, str]:
    args = list(signature.get("args", []) or [])
    if args:
        return {
            str(arg.get("name") or "payload"): _contract_type_from_arg(str(arg.get("name") or "payload"), str(arg.get("annotation") or ""))
            for arg in args
            if isinstance(arg, dict)
        }
    return {"payload": _hint_text(fallback, "InferredInput")}


def _output_contract_from_signature(signature: dict[str, Any], fallback: object) -> dict[str, str]:
    returns = str(signature.get("returns") or "").strip()
    if returns and returns.lower() not in {"any", "typing.any", "none"}:
        return {"result": returns}
    return {"result": _hint_text(fallback, "InferredOutput")}


def _input_contract_from_candidate(candidate: dict[str, Any]) -> dict[str, str]:
    source = str(candidate.get("source") or "")
    signature = dict(candidate.get("signature", {}) or {})
    args = list(signature.get("args", []) or [])
    if args:
        return {
            str(arg.get("name") or "payload"): _contract_type_from_arg(str(arg.get("name") or "payload"), str(arg.get("annotation") or ""))
            for arg in args
            if isinstance(arg, dict)
        }
    return {"payload": _inferred_payload_type(source)}


def _output_contract_from_candidate(candidate: dict[str, Any]) -> dict[str, str]:
    source = str(candidate.get("source") or "")
    returns = str(dict(candidate.get("signature", {}) or {}).get("returns") or "").strip()
    if returns and returns.lower() not in {"any", "typing.any", "none"}:
        return {"result": returns}
    return {"result": _inferred_result_type(source, str(candidate.get("snippet") or ""))}


def _contract_type_from_arg(name: str, annotation: str) -> str:
    annotation = annotation.strip()
    if annotation and annotation.lower() not in {"any", "none"}:
        return annotation
    lowered = name.lower()
    if lowered in {"request", "req"} or "request" in lowered:
        return "RequestLike"
    if lowered in {"response", "resp"} or "response" in lowered:
        return "ResponseLike"
    if "path" in lowered or "file" in lowered or "filename" in lowered:
        return "PathLike"
    if "url" in lowered or "uri" in lowered:
        return "UrlString"
    if "text" in lowered or "message" in lowered or "content" in lowered:
        return "str"
    if "headers" in lowered or "options" in lowered or "config" in lowered or "data" in lowered or "payload" in lowered:
        return "MappingLike"
    if "items" in lowered or "args" in lowered:
        return "SequenceLike"
    if "index" in lowered or "count" in lowered or "line" in lowered:
        return "int"
    return f"Inferred{_camel(name)}"


def _inferred_payload_type(source: str) -> str:
    lowered = source.lower()
    if "rich" in lowered or "console" in lowered or "format" in lowered:
        return "RenderContext"
    if "cli" in lowered or "args" in lowered or "command" in lowered:
        return "CliInput"
    if "exception" in lowered:
        return "ExceptionContext"
    if "schedule" in lowered or lowered.endswith(":at"):
        return "ScheduleTimeInput"
    if "hook" in lowered or "plugin" in lowered:
        return "PluginHookContext"
    return "InferredInput"


def _inferred_result_type(source: str, snippet: str) -> str:
    lowered = source.lower()
    text = snippet.lower()
    if "__rich_console__" in lowered:
        return "Iterable[ConsoleRenderable]"
    if "rich_format" in lowered or "format_help" in lowered:
        return "FormattedHelpRenderable"
    if "format" in lowered:
        return "FormattedText"
    if "interpret" in lowered or "parse" in lowered:
        return "ParsedStructure"
    if lowered.endswith(":at") or "schedule" in lowered:
        return "ScheduleBuilder"
    if "hook" in lowered:
        return "PluginHookResult"
    if "yield " in text:
        return "Iterable[ResultItem]"
    if "return {" in text or "dict(" in text:
        return "MappingLike"
    if "return [" in text:
        return "SequenceLike"
    if "return str" in text or "return \"\"" in text:
        return "str"
    return "InferredOutput"


def _camel(value: str) -> str:
    parts = [part for part in re.split(r"[^a-zA-Z0-9]+", value) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or "Value"


def _side_effect_policy(side_effects: list[Any]) -> dict[str, Any]:
    declared = [str(item) for item in side_effects if item]
    return {
        "declared": declared,
        "idempotency_required": bool(declared),
        "process_boundary_recommended": any(
            item in {"network", "subprocess", "filesystem", "filesystem_write", "database"} for item in declared
        ),
        "retry_policy": "only after checkpoint/idempotency guard" if declared else "safe to retry if pure contract holds",
    }


def _data_lifecycle(brief: dict[str, Any], architecture_decision: dict[str, Any]) -> list[dict[str, Any]]:
    rows = brief.get("data_lifecycle") or architecture_decision.get("data_lifecycle") or []
    if isinstance(rows, list) and rows:
        return [
            {
                "stage": row.get("stage"),
                "shape": row.get("shape"),
                "contract_expectation": _stage_contract_expectation(str(row.get("stage") or "")),
                "evidence": row.get("evidence"),
            }
            for row in rows[:8]
            if isinstance(row, dict)
        ]
    return [
        {
            "stage": "input",
            "shape": "bounded request payload",
            "contract_expectation": "validate before calling selected capability",
            "evidence": "ArchitectureDecisionRecord.data_lifecycle",
        }
    ]


def _state_and_replay_policy(brief: dict[str, Any], architecture_decision: dict[str, Any]) -> list[dict[str, Any]]:
    rows = brief.get("state_model") or architecture_decision.get("state_model") or []
    result = []
    for row in rows[:8] if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        result.append(
            {
                "owner": row.get("owner"),
                "kind": row.get("kind"),
                "lifetime": row.get("lifetime"),
                "resume_policy": row.get("checkpoint_policy") or "recompute unless explicitly persisted",
            }
        )
    return result or [
        {
            "owner": "execution_inputs",
            "kind": "reproducibility_state",
            "lifetime": "scenario_replay",
            "resume_policy": "persist inputs, config, code version, and generated artifacts",
        }
    ]


def _error_model(
    brief: dict[str, Any],
    architecture_decision: dict[str, Any],
    extraction_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = [
        {
            "error": "bad_input",
            "handling": "Reject malformed input at the selected capability boundary with a typed error result.",
            "source": extraction_contract.get("candidate") or "TechnicalSpec.extraction_contract",
        },
        {
            "error": "contract_mismatch",
            "handling": "Stop the handoff and return to SpecWriter/Architect when observed data violates the declared I/O contract.",
            "source": "TechnicalSpec.interface_contracts",
        },
    ]
    for boundary in list(brief.get("external_boundaries") or architecture_decision.get("external_boundaries") or [])[:6]:
        if not isinstance(boundary, dict):
            continue
        rows.append(
            {
                "error": "external_boundary_failure",
                "handling": "Quarantine or isolate the boundary after repeated timeout, dependency drift, or side-effect failure.",
                "source": boundary.get("target"),
            }
        )
    return rows


def _verification_strategy(
    acceptance: list[dict[str, Any]],
    extraction_contract: dict[str, Any],
    work_plan_contract: dict[str, Any],
) -> dict[str, Any]:
    candidate = extraction_contract.get("candidate")
    return {
        "contract_tests": [
            {
                "target": candidate,
                "assertion": "input contract is accepted and output contract is produced",
                "source_acceptance": acceptance[0].get("id") if acceptance else None,
            }
        ],
        "negative_tests": [
            {
                "target": candidate,
                "assertion": "malformed input returns a controlled error instead of an untyped crash",
            }
        ],
        "replay_checks": [
            "Persist input/config/code-version evidence for reproducing the selected scenario.",
            "Do not retry side-effecting boundaries without the declared idempotency policy.",
        ],
        "work_plan_checks": [
            {
                "obligation_id": item.get("id"),
                "target": item.get("target"),
                "assertion": "work-plan obligation is either implemented with evidence or explicitly blocked before handoff",
            }
            for item in list(work_plan_contract.get("obligations", []))[:10]
            if isinstance(item, dict)
        ],
    }


def _handoff_patch_scope(brief: dict[str, Any], work_plan_contract: dict[str, Any]) -> list[str]:
    targets = [_normalize_source_ref(str(item)) for item in list(work_plan_contract.get("targets", [])) if item]
    if targets:
        return targets
    return [_normalize_source_ref(str(item)) for item in list(brief.get("files_or_symbols", [])) if item]


def _step_target(first_slice: dict[str, Any], index: int) -> str | None:
    targets = [str(item) for item in list(first_slice.get("targets", [])) if item]
    if not targets:
        return None
    return targets[min(index - 1, len(targets) - 1)]


def _stage_contract_expectation(stage: str) -> str:
    lowered = stage.lower()
    if "input" in lowered:
        return "input must be validated and recorded before transformation"
    if "output" in lowered:
        return "output must match declared schema or artifact path policy"
    return "intermediate shape must be named before handoff"


def _hint_text(value: object, default: str) -> str:
    if isinstance(value, list) and value:
        return str(value[0])
    text = str(value or "").strip()
    return text or default


def _rank_extraction_candidates(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for index, row in enumerate(evidence):
        candidate = dict(row)
        score = 0
        reasons = []
        kind = str(candidate.get("kind") or "")
        side_effects = list(candidate.get("side_effects", []) or [])
        signature = dict(candidate.get("signature", {}) or {})
        claims = [str(item) for item in candidate.get("claims", []) or []]

        if kind == "pure_transform":
            score += 40
            reasons.append("pure transform candidate")
        elif kind == "central_flow_node":
            score += 45
            reasons.append("central flow node with subsystem-level evidence")
        elif kind == "broad_function":
            score += 38
            reasons.append("broad function can anchor a meaningful first slice")
        else:
            score += 5
            reasons.append("available source evidence")

        if candidate.get("central_flow_node"):
            score += 20
            reasons.append("central flow evidence available")
        if candidate.get("mixed_responsibilities"):
            score += 12
            reasons.append("mixed-responsibility evidence available")
        if candidate.get("process_boundary_reasons"):
            score += 8
            reasons.append("process-boundary evidence available")
        if candidate.get("candidate_level"):
            score += _candidate_level_bonus(str(candidate.get("candidate_level")))
            reasons.append(f"ProjectMapReport ranked as {candidate.get('candidate_level')}")
        if candidate.get("candidate_score") is not None:
            score += min(int(candidate.get("candidate_score") or 0), 100) // 20
            reasons.append("ProjectMapReport candidate score available")

        if not side_effects:
            score += 25
            reasons.append("no declared side effects")
        else:
            score -= 20
            reasons.append("declared side effects require tighter isolation")

        if signature.get("args"):
            score += 10
            reasons.append("input contract can be inferred from signature")
        if signature.get("returns"):
            score += 10
            reasons.append("output contract can be inferred from signature")
        if candidate.get("snippet"):
            score += 5
            reasons.append("snippet available for source-backed review")
        unresolved_names = _high_confidence_unresolved_snippet_names(candidate)
        if unresolved_names:
            score -= 70
            reasons.append("snippet references unresolved names: " + ", ".join(unresolved_names[:6]))
        if candidate.get("callers"):
            score += 5
            reasons.append("caller context available")
        name_score, name_reasons = _name_and_contract_score(str(candidate.get("source") or ""), signature, side_effects)
        score += name_score
        reasons.extend(name_reasons)
        if any("idempotency" in claim.lower() for claim in claims):
            score -= 10
            reasons.append("idempotency risk claim present")
        if any("side effect" in claim.lower() for claim in claims):
            score -= 10
            reasons.append("side-effect risk claim present")
        policy_score, policy_reasons = _operational_boundary_score(str(candidate.get("source") or ""), signature, claims)
        score += policy_score
        reasons.extend(policy_reasons)
        shape_score, shape_reasons = _architecture_shape_score(str(candidate.get("source") or ""))
        score += shape_score
        reasons.extend(shape_reasons)

        ranked.append(
            {
                "source": candidate.get("source"),
                "kind": candidate.get("kind"),
                "score": score,
                "reasons": reasons,
                "side_effects": side_effects,
                "evidence": candidate,
                "index": index,
            }
        )
    return sorted(ranked, key=lambda item: (-int(item["score"]), int(item["index"]), str(item.get("source") or "")))


def _high_confidence_unresolved_snippet_names(candidate: dict[str, Any]) -> list[str]:
    snippet = _snippet_text(candidate.get("snippet"))
    if not snippet or "..." in snippet:
        return []
    try:
        tree = ast.parse(snippet)
    except SyntaxError:
        return []
    local_names = set(_signature_arg_names(candidate))
    loaded_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                loaded_names.add(node.id)
            elif isinstance(node.ctx, (ast.Store, ast.Del)):
                local_names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            local_names.add(node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_names.update(arg.arg for arg in node.args.args)
                local_names.update(arg.arg for arg in node.args.kwonlyargs)
                if node.args.vararg:
                    local_names.add(node.args.vararg.arg)
                if node.args.kwarg:
                    local_names.add(node.args.kwarg.arg)
        elif isinstance(node, ast.Import):
            local_names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            local_names.update(alias.asname or alias.name for alias in node.names)
    unresolved = sorted(
        name
        for name in loaded_names
        if name not in local_names and name not in _BUILTIN_NAMES and name not in _ALLOWED_EXTERNAL_SNIPPET_NAMES
    )
    unresolved_set = set(unresolved)
    for required_set in _HIGH_CONFIDENCE_UNRESOLVED_SETS:
        if required_set.issubset(unresolved_set):
            return [name for name in unresolved if name in required_set]
    return []


def _snippet_text(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or "")
    return str(value or "")


def _signature_arg_names(candidate: dict[str, Any]) -> list[str]:
    signature = dict(candidate.get("signature", {}) or {})
    names = []
    for row in signature.get("args", []) or []:
        if isinstance(row, dict) and row.get("name"):
            names.append(str(row["name"]))
    return names


def _semantic_rerank_candidates(ranked: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(ranked) < 2:
        return ranked
    evidence_sources = [str(row.get("source")) for row in evidence if row.get("source")]
    ranked_sources = [str(row.get("source")) for row in ranked if row.get("source")]
    enriched = []
    for item in ranked:
        candidate = dict(item)
        quality = semantic_target_quality_report(
            str(candidate.get("source") or ""),
            ranked_candidates=ranked_sources,
            source_evidence=evidence_sources,
            selection_reason="; ".join(str(reason) for reason in candidate.get("reasons", [])),
        )
        candidate["semantic_quality"] = quality
        candidate["semantic_score"] = int(quality.get("score") or 0)
        candidate["semantic_status"] = str(quality.get("status") or "")
        enriched.append(candidate)
    first = enriched[0]
    if first["semantic_status"] == "strong":
        return enriched
    replacement = _best_semantic_replacement(enriched)
    if replacement is None or replacement is first:
        return enriched
    replacement["reasons"] = [
        *list(replacement.get("reasons", [])),
        "semantic rerank selected a stronger bounded first-slice target",
    ]
    return [replacement, *[item for item in enriched if item is not replacement]]


def _best_semantic_replacement(ranked: list[dict[str, Any]]) -> dict[str, Any] | None:
    first = ranked[0]
    first_semantic = int(first.get("semantic_score") or 0)
    first_score = int(first.get("score") or 0)
    candidates = [
        item
        for item in ranked[1:12]
        if _semantic_candidate_is_better(item, first_semantic=first_semantic, first_score=first_score)
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (
            0 if item.get("semantic_status") == "strong" else 1,
            -int(item.get("semantic_score") or 0),
            -int(item.get("score") or 0),
            int(item.get("index") or 0),
        ),
    )[0]


def _semantic_candidate_is_better(item: dict[str, Any], *, first_semantic: int, first_score: int) -> bool:
    status = str(item.get("semantic_status") or "")
    semantic_score = int(item.get("semantic_score") or 0)
    score = int(item.get("score") or 0)
    if status == "strong" and semantic_score >= first_semantic + 8 and score >= first_score - 35:
        return True
    if semantic_score >= first_semantic + 18 and score >= first_score - 20:
        return True
    return False


def _architecture_shape_score(source: str) -> tuple[int, list[str]]:
    lowered = source.lower()
    score = 0
    reasons: list[str] = []
    if any(token in lowered for token in ("service.py:", "providers/factory.py", "import_indoc.py:parse_file")):
        score += 35
        reasons.append("architecture-useful service/parser/factory boundary")
    if any(token in lowered for token in ("resolve", "build_providers", "parse_file", "features_for_view", "incident_features")):
        score += 18
        reasons.append("domain boundary function name")
    if any(token in lowered for token in ("api.py:describe_module", "_plugin_metadata.py", "debug_", "smoke")):
        score -= 35
        reasons.append("generic introspection/debug helper is lower priority")
    if "downloader.py:worker" in lowered:
        score -= 20
        reasons.append("background worker is evidence, not first writable contract")
    return score, reasons


def _requirement_statement(requirement: str, source: object) -> str:
    source_text = str(source or "").strip()
    if requirement == "Capability candidate requires TechnicalSpec." and source_text:
        return f"{source_text} must have explicit input/output contract, side-effect policy, and Foundry quality gate."
    if requirement == "Risk must be addressed or accepted before promotion." and source_text:
        return f"Risk from {source_text} must be mitigated or explicitly accepted before promotion."
    return requirement


def _acceptance_targets(brief: dict[str, Any], traceability: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for row in traceability[:40]:
        source = row.get("source")
        requirement = str(row.get("acceptance") or row.get("requirement") or "")
        rows.append({"source": str(source or ""), "criterion": _acceptance_statement(requirement, source)})
    seen_sources = {row["source"] for row in rows if row.get("source")}
    for source in brief.get("files_or_symbols", []) or []:
        source_text = str(source or "")
        if not source_text or source_text in seen_sources:
            continue
        rows.append({"source": source_text, "criterion": _acceptance_statement("Capability candidate requires TechnicalSpec.", source_text)})
        seen_sources.add(source_text)
    if rows:
        return rows
    return [
        {"source": "spec_writer_brief", "criterion": str(item)}
        for item in brief.get("acceptance_targets", [])
        if item
    ]


def _acceptance_statement(requirement: str, source: object) -> str:
    source_text = str(source or "").strip()
    if requirement == "Capability candidate requires TechnicalSpec." and source_text:
        return f"{source_text} has a bounded TechnicalSpec with source evidence, input contract, output contract, and negative-test expectation."
    if requirement == "Risk must be addressed or accepted before promotion." and source_text:
        return f"{source_text} risk is represented in constraints, acceptance criteria, or non-goals before any implementation handoff."
    return requirement or f"{source_text} is covered by the TechnicalSpec."


def _spec_traceability(
    traceability: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    by_source = _acceptance_by_source(acceptance)
    fallback_ids = [str(row.get("id") or "") for row in acceptance if isinstance(row, dict)]
    for index, row in enumerate(traceability[: len(acceptance)]):
        source = str(row.get("source") or "")
        rows.append(
            {
                "source": row.get("source"),
                "requirement": row.get("requirement"),
                "acceptance_id": by_source.get(source) or fallback_ids[min(index, len(fallback_ids) - 1)] if fallback_ids else None,
            }
        )
    return rows


def _acceptance_by_source(acceptance: list[dict[str, Any]]) -> dict[str, str]:
    result = {}
    for row in acceptance:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "")
        item_id = str(row.get("id") or "")
        if source and item_id and source not in result:
            result[source] = item_id
    return result

