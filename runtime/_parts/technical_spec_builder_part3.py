from __future__ import annotations

import ast
import builtins
import re
from typing import Any
from runtime.source_contract_semantics import infer_source_contract
from runtime.role_spec_writer_ranking import (
    candidate_level_bonus as _candidate_level_bonus,
    name_and_contract_score as _name_and_contract_score,
    operational_boundary_score as _operational_boundary_score,
)
from runtime.role_skill_common import now_iso
from runtime.semantic_target_profiles import contract_for_target
from runtime.target_quality import semantic_target_quality_report
from runtime.technical_spec_policy import load_technical_spec_policy, policy_list, policy_rules

_BUILTIN_NAMES = set(dir(builtins))
TECHNICAL_SPEC_POLICY = load_technical_spec_policy()
SNIPPET_POLICY = dict(TECHNICAL_SPEC_POLICY["snippet_analysis"])
CONTRACT_TYPE_POLICY = dict(TECHNICAL_SPEC_POLICY["contract_type_inference"])
SEMANTIC_RERANK_POLICY = dict(TECHNICAL_SPEC_POLICY["semantic_rerank"])
FIRST_SLICE_SCOPE_POLICY = dict(TECHNICAL_SPEC_POLICY.get("first_slice_scope") or {})
ARCHITECTURE_SHAPE_POLICY = dict(TECHNICAL_SPEC_POLICY["architecture_shape_score"])
SIDE_EFFECT_PROCESS_BOUNDARY = set(policy_list(TECHNICAL_SPEC_POLICY, "side_effect_process_boundary"))
ALLOWED_EXTERNAL_SNIPPET_NAMES = {str(item) for item in SNIPPET_POLICY.get("allowed_external_names", [])}
HIGH_CONFIDENCE_UNRESOLVED_SETS = tuple(
    frozenset(str(item) for item in row)
    for row in SNIPPET_POLICY.get("high_confidence_unresolved_sets", [])
    if isinstance(row, list)
)
IGNORED_RETURN_ANNOTATIONS = set(policy_list(CONTRACT_TYPE_POLICY, "ignored_return_annotations"))
ARGUMENT_TYPE_RULES = policy_rules(CONTRACT_TYPE_POLICY, "argument_rules")
PAYLOAD_TYPE_RULES = policy_rules(CONTRACT_TYPE_POLICY, "payload_rules")
RESULT_TYPE_RULES = policy_rules(CONTRACT_TYPE_POLICY, "result_rules")

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
    args = _contract_args(signature)
    if args:
        return {
            str(arg.get("name") or "payload"): _contract_type_from_arg(str(arg.get("name") or "payload"), str(arg.get("annotation") or ""))
            for arg in args
            if isinstance(arg, dict)
        }
    return {}

def _output_contract_from_signature(signature: dict[str, Any], fallback: object) -> dict[str, str]:
    returns = str(signature.get("returns") or "").strip()
    if returns and returns.lower() not in IGNORED_RETURN_ANNOTATIONS:
        return {"result": returns}
    return {"result": _hint_text(fallback, "InferredOutput")}

def _input_contract_from_candidate(candidate: dict[str, Any]) -> dict[str, str]:
    source = str(candidate.get("source") or "")
    signature = dict(candidate.get("signature", {}) or {})
    semantic = infer_source_contract(candidate)
    documented = dict(semantic.get("docstring_argument_types") or {})
    constrained = dict(semantic.get("argument_constraint_types") or {})
    usage_types = dict(semantic.get("argument_usage_types") or {})
    owner = str(semantic.get("owner_class") or "")
    args = _contract_args(signature)
    if args:
        contract = {
            str(arg.get("name") or "payload"): _candidate_argument_type(arg, documented, constrained, usage_types)
            for arg in args
            if isinstance(arg, dict)
        }
        return {"receiver_state": f"{owner}State", **contract} if owner else contract
    if owner:
        return {"receiver_state": f"{owner}State"}
    if "args" in signature:
        return {"call_context": "NoArguments"}
    return {"call_context": _inferred_payload_type(source)}

def _candidate_argument_type(
    arg: dict[str, Any], documented: dict[str, str], constrained: dict[str, str], usage_types: dict[str, str]
) -> str:
    name = str(arg.get("name") or "payload")
    annotation = str(arg.get("annotation") or "")
    if annotation and annotation.lower() not in IGNORED_RETURN_ANNOTATIONS:
        return annotation
    return documented.get(name) or constrained.get(name) or usage_types.get(name) or _contract_type_from_arg(name, annotation)

def _contract_args(signature: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        item
        for item in [*list(signature.get("args", []) or []), *list(signature.get("kwonlyargs", []) or [])]
        if isinstance(item, dict) and str(item.get("name") or "") not in {"self", "cls"}
    ]
    return rows

def _output_contract_from_candidate(candidate: dict[str, Any]) -> dict[str, str]:
    semantic = infer_source_contract(candidate)
    inferred = str(semantic.get("inferred_output_type") or "").strip()
    source = str(candidate.get("source") or "")
    policy_inferred = _inferred_result_type(source, str(candidate.get("snippet") or ""))
    if inferred in {"MappingLike", "SequenceLike", "TupleLike", "SetLike"} and policy_inferred != "InferredOutput":
        return {"result": policy_inferred}
    if inferred and inferred.lower() not in IGNORED_RETURN_ANNOTATIONS:
        return {"result": inferred}
    return {"result": policy_inferred}

def _contract_type_from_arg(name: str, annotation: str) -> str:
    annotation = annotation.strip()
    if annotation and annotation.lower() not in IGNORED_RETURN_ANNOTATIONS:
        return annotation
    lowered = name.lower()
    for rule in ARGUMENT_TYPE_RULES:
        if _matches_text_rule(lowered, rule, exact_field="exact", contains_field="contains_any"):
            return str(rule.get("type") or f"Inferred{_camel(name)}")
    return f"Inferred{_camel(name)}"

def _inferred_payload_type(source: str) -> str:
    lowered = source.lower()
    for rule in PAYLOAD_TYPE_RULES:
        if _matches_source_snippet_rule(lowered, "", rule):
            return str(rule.get("type") or "InferredInput")
    return "InferredInput"

def _inferred_result_type(source: str, snippet: str) -> str:
    lowered = source.lower()
    text = snippet.lower()
    for rule in RESULT_TYPE_RULES:
        if _matches_source_snippet_rule(lowered, text, rule):
            return str(rule.get("type") or "InferredOutput")
    return "InferredOutput"

def _matches_text_rule(text: str, rule: dict[str, Any], *, exact_field: str, contains_field: str) -> bool:
    exact = {str(item).lower() for item in list(rule.get(exact_field) or [])}
    if text in exact:
        return True
    return any(str(token).lower() in text for token in list(rule.get(contains_field) or []))

def _matches_source_snippet_rule(source: str, snippet: str, rule: dict[str, Any]) -> bool:
    source_tokens = [str(token).lower() for token in list(rule.get("source_contains_any") or [])]
    suffixes = [str(token).lower() for token in list(rule.get("source_suffixes") or [])]
    snippet_tokens = [str(token).lower() for token in list(rule.get("snippet_contains_any") or [])]
    source_match = not source_tokens or any(token in source for token in source_tokens)
    suffix_match = not suffixes or any(source.endswith(token) for token in suffixes)
    snippet_match = not snippet_tokens or any(token in snippet for token in snippet_tokens)
    if (source_tokens or suffixes or snippet_tokens) and source_match and suffix_match and snippet_match:
        return True
    return False

def _camel(value: str) -> str:
    parts = [part for part in re.split(r"[^a-zA-Z0-9]+", value) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or "Value"

def _side_effect_policy(side_effects: list[Any]) -> dict[str, Any]:
    declared = [str(item) for item in side_effects if item]
    mutating = set(policy_list(TECHNICAL_SPEC_POLICY, "side_effect_idempotency_required"))
    idempotency_required = bool(set(declared) & mutating)
    return {
        "declared": declared,
        "idempotency_required": idempotency_required,
        "process_boundary_recommended": any(item in SIDE_EFFECT_PROCESS_BOUNDARY for item in declared),
        "retry_policy": "only after checkpoint/idempotency guard" if idempotency_required else "safe to retry if read snapshot or pure contract holds",
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

def _handoff_patch_scope(
    brief: dict[str, Any],
    work_plan_contract: dict[str, Any],
    *,
    extraction_contract: dict[str, Any] | None = None,
) -> list[str]:
    targets = [_normalize_source_ref(str(item)) for item in list(work_plan_contract.get("targets", [])) if item]
    if not targets:
        targets = [_normalize_source_ref(str(item)) for item in list(brief.get("files_or_symbols", [])) if item]
    ranked_sources = _ranked_contract_sources(dict(extraction_contract or {}))
    scope = _dedupe([*targets, *ranked_sources])
    return scope[:32]

def _ranked_contract_sources(extraction_contract: dict[str, Any]) -> list[str]:
    sources = []
    candidate = _normalize_source_ref(str(extraction_contract.get("candidate") or ""))
    if candidate:
        sources.append(candidate)
    for source in list(extraction_contract.get("supporting_sources") or []):
        normalized = _normalize_source_ref(str(source or ""))
        if normalized and _implementation_source(normalized):
            sources.append(normalized)
    for row in list(extraction_contract.get("ranked_candidates", [])):
        if not isinstance(row, dict):
            continue
        source = _normalize_source_ref(str(row.get("source") or ""))
        if not source or not _implementation_source(source):
            continue
        sources.append(source)
    return _dedupe(sources)
