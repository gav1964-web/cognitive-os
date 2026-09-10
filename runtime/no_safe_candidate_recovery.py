"""Bounded Researcher-to-Architect recovery for exhausted first-slice selection."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RECOVERY_TRIGGER = "no_semantically_safe_candidate_in_approved_first_slice"


def run_no_safe_candidate_recovery(
    *,
    project_root: Path,
    project: str,
    technical_spec: dict[str, Any],
    control_plane: dict[str, Any],
) -> dict[str, Any]:
    """Create a read-only recovery route while preserving the controlled stop."""
    request = dict(technical_spec.get("first_slice_reselection_request") or {})
    escalation = dict(control_plane.get("semantic_escalation") or {})
    if not _is_applicable(request, escalation):
        return {
            "artifact_type": "NoSafeCandidateRecoveryRoute",
            "status": "not_applicable",
            "project": project,
            "reason": "no_exhausted_no_safe_candidate_escalation",
            "source_changes": False,
            "kb_changes": False,
        }

    packet = _build_failure_packet(project, request)
    hypothesis = _build_research_hypothesis(project_root, packet)
    gate = _run_architect_reentry_gate(project_root, packet, hypothesis)
    candidate = _build_provisional_candidate(packet, hypothesis, gate)
    developer_request = _build_developer_request(packet, hypothesis, gate)
    return {
        "artifact_type": "NoSafeCandidateRecoveryRoute",
        "status": "bounded_rework_ready" if gate["status"] == "accepted_for_bounded_rework" else "controlled_stop",
        "created_at": _now(),
        "project": project,
        "route": ["reviewer", "researcher", "architect", "developer", "architect"],
        "failure_packet": packet,
        "research_hypothesis": hypothesis,
        "architect_reentry_gate": gate,
        "provisional_candidate": candidate,
        "developer_request": developer_request,
        "fallback": {
            "status": "blocked_no_safe_candidate",
            "active_until": "source_backed_candidate_passes_normal_architect_reselection",
        },
        "source_changes": False,
        "kb_changes": False,
        "automatic_promotion": False,
    }


def _is_applicable(request: dict[str, Any], escalation: dict[str, Any]) -> bool:
    reasons = {str(item) for item in escalation.get("reasons", [])}
    return (
        request.get("trigger") == RECOVERY_TRIGGER
        and request.get("resolution_status") == "exhausted"
        and request.get("terminal") is True
        and "no_safe_source_specific_candidate" in reasons
    )


def _build_failure_packet(project: str, request: dict[str, Any]) -> dict[str, Any]:
    outcome = dict(request.get("outcome") or {})
    viability = [dict(row) for row in outcome.get("candidate_viability", []) if isinstance(row, dict)]
    rejected = sorted(
        viability,
        key=lambda row: (int(row.get("semantic_score") or 0), int(row.get("contract_shape_score") or 0)),
        reverse=True,
    )
    return {
        "artifact_type": "NoSafeCandidateFailurePacket",
        "status": "requested",
        "created_at": _now(),
        "project": project,
        "trigger": request.get("trigger"),
        "reselection_status": request.get("resolution_status"),
        "rejected_candidates": [
            {
                "target": row.get("target"),
                "semantic_score": row.get("semantic_score"),
                "viability_status": row.get("status"),
                "observed_side_effects": list(row.get("observed_side_effects") or []),
                "blocking_rules": [
                    str(rule.get("rule_id"))
                    for rule in row.get("matched_rules", [])
                    if isinstance(rule, dict) and rule.get("rule_id")
                ],
            }
            for row in rejected
        ],
        "research_question": "Can the highest-value rejected callable be decomposed into a pure core and explicit effect adapters?",
        "allowed_outcomes": ["decomposition_hypothesis", "knowledge_gap"],
        "forbidden_actions": ["edit_source", "select_nonexistent_callable", "mutate_kb", "bypass_architect_gate"],
        "return_to_role": "architect",
    }


def _build_research_hypothesis(project_root: Path, packet: dict[str, Any]) -> dict[str, Any]:
    rejected = list(packet.get("rejected_candidates") or [])
    origin = str(dict(rejected[0]).get("target") or "") if rejected else ""
    source = _read_function(project_root, origin)
    if source is None:
        return {
            "artifact_type": "SemanticDecompositionHypothesis",
            "status": "knowledge_gap",
            "origin_target": origin,
            "confidence": 0.0,
            "evidence": [],
            "risks": ["source-backed callable could not be resolved"],
            "return_to_gate": True,
        }
    path_text, function = origin.split(":", 1)
    effects = sorted(set(dict(rejected[0]).get("observed_side_effects") or []))
    proposed_symbol = _proposed_symbol(function, source["transform_signals"])
    return {
        "artifact_type": "SemanticDecompositionHypothesis",
        "status": "proposed",
        "origin_target": origin,
        "hypothesis_type": "pure_core_with_effect_adapters",
        "proposed_target": f"{path_text}:{proposed_symbol}",
        "pure_core_contract": {
            "input": _proposed_input_contract(proposed_symbol),
            "output": _proposed_output_contract(proposed_symbol),
            "side_effects": [],
        },
        "effect_adapters": [
            {"effect": effect, "boundary": _adapter_boundary(effect)} for effect in effects
        ],
        "evidence": [
            f"{origin}:source_lines={source['start_line']}-{source['end_line']}",
            f"{origin}:effectful_calls={','.join(source['effectful_calls'])}",
            f"{origin}:transform_signals={','.join(source['transform_signals'])}",
        ],
        "confidence": 0.86 if effects and source["transform_signals"] else 0.58,
        "risks": [
            "proposed callable does not exist until Developer implements the decomposition",
            "subprocess ordering and output behavior must remain explicit at the orchestration boundary",
        ],
        "actions": ["request_bounded_decomposition", "return_to_architect_gate"],
        "return_to_gate": True,
    }


def _run_architect_reentry_gate(
    project_root: Path, packet: dict[str, Any], hypothesis: dict[str, Any]
) -> dict[str, Any]:
    origin = str(hypothesis.get("origin_target") or "")
    proposed = str(hypothesis.get("proposed_target") or "")
    adapters = list(hypothesis.get("effect_adapters") or [])
    rejected = list(packet.get("rejected_candidates") or [])
    expected_effects = set(dict(rejected[0]).get("observed_side_effects") or []) if rejected else set()
    checks = {
        "failure_packet_is_bounded": bool(rejected) and packet.get("reselection_status") == "exhausted",
        "origin_is_source_backed": _read_function(project_root, origin) is not None,
        "hypothesis_returns_to_gate": hypothesis.get("return_to_gate") is True,
        "pure_core_declares_no_effects": dict(hypothesis.get("pure_core_contract") or {}).get("side_effects") == [],
        "effect_adapters_cover_observed_effects": expected_effects == {
            str(dict(row).get("effect")) for row in adapters
        },
        "candidate_is_not_falsely_source_backed": bool(proposed) and _read_function(project_root, proposed) is None,
        "confidence_is_sufficient": float(hypothesis.get("confidence") or 0.0) >= 0.8,
    }
    accepted = all(checks.values())
    return {
        "artifact_type": "ArchitectRecoveryGate",
        "status": "accepted_for_bounded_rework" if accepted else "rejected",
        "authority": "architect",
        "checks": checks,
        "can_replace_controlled_stop": False,
        "can_enter_developer": accepted,
        "can_enter_implementer": False,
        "required_reentry": "normal_source_backed_first_slice_reselection",
    }


def _build_provisional_candidate(
    packet: dict[str, Any], hypothesis: dict[str, Any], gate: dict[str, Any]
) -> dict[str, Any]:
    accepted = gate.get("status") == "accepted_for_bounded_rework"
    return {
        "artifact_type": "ProvisionalExtractionCandidate",
        "status": "verified_for_bounded_implementation" if accepted else "rejected",
        "candidate": hypothesis.get("proposed_target"),
        "origin_target": hypothesis.get("origin_target"),
        "verification_scope": "architecture_and_source_decomposition_plan",
        "source_backed": False,
        "selection_eligible": False,
        "promotion_gate": {
            "automatic_promotion": False,
            "required_checks": [
                "developer_adds_source_backed_callable",
                "pure_contract_tests_pass",
                "effect_adapter_tests_pass",
                "normal_architect_reselection_selects_candidate",
            ],
        },
        "evidence_ref": packet.get("artifact_type"),
    }


def _build_developer_request(
    packet: dict[str, Any], hypothesis: dict[str, Any], gate: dict[str, Any]
) -> dict[str, Any] | None:
    if gate.get("status") != "accepted_for_bounded_rework":
        return None
    return {
        "artifact_type": "DeveloperImprovementRequest",
        "status": "requested",
        "request_id": "decompose_no_safe_candidate",
        "missing_capability": hypothesis.get("proposed_target"),
        "problem": "The only source-backed callable mixes transformation logic with external effects.",
        "evidence_refs": [packet.get("artifact_type"), hypothesis.get("origin_target")],
        "suggested_work": [
            "extract the proposed pure core without changing observable orchestration behavior",
            "keep filesystem and subprocess operations behind explicit adapters",
            "add pure-core and adapter-boundary tests",
        ],
        "acceptance_focus": list(dict(hypothesis.get("promotion_gate") or {}).get("required_checks") or [])
        or ["source-backed callable exists", "normal Architect reselection accepts it"],
        "patch_recipe": {
            "id": _patch_recipe_id(str(hypothesis.get("proposed_target") or "")),
            "origin_target": hypothesis.get("origin_target"),
            "created_target": hypothesis.get("proposed_target"),
            "execution_mode": "isolated_sandbox_no_source_edit",
        },
        "requires_developer": True,
        "forbidden_auto_actions": ["edit_source", "mutate_registry", "promote_to_kb"],
        "next_step": "developer implements bounded change, then Architect reruns the normal gate",
    }


def _read_function(project_root: Path, target: str) -> dict[str, Any] | None:
    if ":" not in target:
        return None
    path_text, symbol = target.split(":", 1)
    root = project_root.resolve()
    path = (root / path_text).resolve()
    if root not in path.parents or not path.is_file():
        return None
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return None
    node = next(
        (item for item in tree.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == symbol),
        None,
    )
    if node is None:
        return None
    calls = sorted({_call_name(item.func) for item in ast.walk(node) if isinstance(item, ast.Call)})
    effectful = [call for call in calls if any(marker in call for marker in ("read_text", "write_text", "subprocess."))]
    transforms = sorted({
        marker
        for marker, kind in (
            ("splitlines", "splitlines"),
            ("split", "split"),
            ("strip", "strip"),
            ("serialize_json", "json.dumps"),
            ("parse_json", "json.loads"),
            ("record_build", "Dict"),
        )
        if any(
            (isinstance(item, ast.Call) and kind != "Dict" and _call_name(item.func).endswith(kind))
            or (kind == "Dict" and isinstance(item, ast.Dict))
            for item in ast.walk(node)
        )
    })
    return {
        "start_line": node.lineno,
        "end_line": getattr(node, "end_lineno", node.lineno),
        "effectful_calls": effectful,
        "transform_signals": transforms,
    }


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _adapter_boundary(effect: str) -> str:
    if effect == "subprocess":
        return "process_runner"
    if effect in {"filesystem", "filesystem_read", "filesystem_write"}:
        return "file_gateway"
    return f"{effect}_adapter"


def _proposed_symbol(origin_symbol: str, transform_signals: list[str]) -> str:
    signals = set(transform_signals)
    if "parse_json" in signals:
        return "parse_json"
    if "serialize_json" in signals and "record_build" not in signals:
        return "serialize_json"
    if {"record_build", "strip"} <= signals:
        return "normalize_record"
    if "serialize_json" in signals:
        return "serialize_json"
    if "splitlines" in signals:
        return "split_lines"
    if "split" in signals:
        return "parse_rows"
    return f"{origin_symbol}_core"


def _proposed_input_contract(symbol: str) -> str:
    return {
        "normalize_record": "parsed_row",
        "serialize_json": "json_serializable_value",
        "parse_json": "json_text",
        "split_lines": "text",
    }.get(symbol, "text_or_parsed_rows")


def _proposed_output_contract(symbol: str) -> str:
    return {
        "normalize_record": "normalized_record",
        "serialize_json": "json_text",
        "parse_json": "json_value",
        "split_lines": "text_lines",
    }.get(symbol, "normalized_records")


def _patch_recipe_id(proposed_target: str) -> str:
    symbol = proposed_target.rpartition(":")[2]
    return {
        "normalize_record": "extract_append_mapping_helper",
        "serialize_json": "extract_json_dumps_helper",
        "parse_json": "extract_json_loads_helper",
        "split_lines": "extract_splitlines_helper",
    }.get(symbol, "unsupported_recovery_patch")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
