"""Greenfield Architect -> SpecWriter pipeline."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .greenfield_architecture_builder import build_product_architecture_record
from .greenfield_documents import write_product_architecture_document, write_product_technical_spec_document
from .greenfield_spec_builder import build_product_technical_spec
from .l4_semantic_validation import validate_l45_semantic_proposal
from .role_skill_common import write_role_artifact
from .semantic_evidence_pack import build_semantic_evidence_pack
from .semantic_reasoner import build_developer_improvement_request, build_semantic_hypothesis_request, run_semantic_reasoner


def run_greenfield_role_pipeline(
    *,
    root: Path,
    prompt: str,
    write: bool = False,
    question_mode: str = "continue_with_assumptions",
    include_debug_artifacts: bool = False,
    use_l45_model: bool | None = None,
    require_specific_pattern: bool = True,
) -> dict[str, Any]:
    if use_l45_model is None:
        use_l45_model = os.environ.get("COGNITIVE_OS_USE_L45_LLM", "").lower() in {"1", "true", "yes", "on"}
    architecture = build_product_architecture_record(prompt, question_mode=question_mode)
    semantic_gap = require_specific_pattern and _is_generic_greenfield_pattern(architecture)
    semantic_evidence_pack = None
    semantic_request = None
    semantic_proposal = None
    semantic_validation = None
    developer_improvement_request = None
    if semantic_gap and architecture.get("status") == "ok":
        control_plane = _greenfield_semantic_gap_decision(prompt=prompt, architecture=architecture)
        semantic_evidence_pack = build_semantic_evidence_pack(
            control_plane_decision=control_plane,
            prompt=prompt,
            prompt_adequacy=dict(architecture.get("prompt_adequacy") or {}),
            supported_templates=[],
            known_templates=[],
            context={"pattern_id": architecture.get("pattern_id"), "route": "greenfield_architect_to_specwriter"},
        )
        semantic_request = build_semantic_hypothesis_request(
            control_plane_decision=control_plane,
            context={
                "prompt": prompt,
                "architecture": _architecture_gap_context(architecture),
                "evidence_pack": semantic_evidence_pack,
            },
        )
        semantic_proposal = run_semantic_reasoner(request=semantic_request, use_model=use_l45_model) if semantic_request else None
        semantic_validation = (
            validate_l45_semantic_proposal(request=semantic_request, proposal=semantic_proposal)
            if semantic_request is not None and semantic_proposal is not None
            else None
        )
        developer_improvement_request = (
            build_developer_improvement_request(semantic_proposal or {})
            if semantic_validation is not None
            and semantic_validation.get("accepted_action") == "record_developer_improvement_request"
            else None
        )
    should_build_spec = architecture["status"] == "ok" and not semantic_gap
    spec = build_product_technical_spec(architecture) if should_build_spec else None
    paths: dict[str, str] = {}
    docs: dict[str, str] = {}
    if write:
        paths["product_architecture"] = write_role_artifact(root, "architect", architecture).as_posix()
        docs["product_architecture"] = write_product_architecture_document(root=root, architecture=architecture).as_posix()
        if spec is not None:
            paths["product_technical_spec"] = write_role_artifact(root, "spec_writer", spec).as_posix()
            docs["product_technical_spec"] = write_product_technical_spec_document(root=root, technical_spec=spec).as_posix()
    question_policy = dict(architecture.get("open_question_policy", {}))
    report = {
        "artifact_type": "GreenfieldRolePipelineReport",
        "status": _report_status(architecture, spec),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt": prompt,
        "milestone": "UserPrompt -> ProductArchitectureRecord -> ProductTechnicalSpec",
        "open_question_policy": question_policy,
        "next_action": _next_action(architecture, semantic_gap=semantic_gap, developer_request=developer_improvement_request),
        "clarification_prompt": question_policy.get("clarification_prompt")
        if question_policy.get("decision") == "ask_user_before_spec"
        else None,
        "artifacts": {
            "product_architecture": _summary(architecture, paths.get("product_architecture")),
            "product_technical_spec": _summary(spec, paths.get("product_technical_spec")) if spec is not None else None,
        },
        "human_documents": docs,
        "selected_architecture_style": architecture.get("architecture_style"),
        "primary_contract": spec.get("primary_contract", {}) if spec is not None else {},
        "safety": {
            "source_project_modified": False,
            "registry_changed": False,
            "spec_writer_started": spec is not None,
            "implementation_started": False,
            "llm_invoked": bool(
                semantic_proposal
                and dict(semantic_proposal.get("hardening") or {}).get("raw_model_output_used")
            ),
        },
    }
    if semantic_gap:
        report["semantic_gap"] = {
            "reason_code": "greenfield_pattern_missing",
            "pattern_id": architecture.get("pattern_id"),
            "handled_by": "L4.5 SemanticHypothesisRequest",
            "llm_requested": bool(use_l45_model),
        }
    if semantic_evidence_pack is not None:
        report["semantic_evidence_pack"] = semantic_evidence_pack
    if semantic_request is not None:
        report["semantic_hypothesis_request"] = semantic_request
    if semantic_proposal is not None:
        report["semantic_hypothesis_proposal"] = semantic_proposal
    if semantic_validation is not None:
        report["l4_semantic_validation"] = semantic_validation
    if developer_improvement_request is not None:
        report["developer_improvement_request"] = developer_improvement_request
    if write:
        out_dir = root / "artifacts" / "roles" / "greenfield"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"greenfield_role_pipeline_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    if include_debug_artifacts:
        report["_debug_artifacts"] = {
            "product_architecture": architecture,
            "product_technical_spec": spec,
        }
    return report


def _report_status(architecture: dict[str, Any], spec: dict[str, Any] | None) -> str:
    if architecture.get("status") == "needs_clarification":
        return "needs_clarification"
    if _is_generic_greenfield_pattern(architecture) and spec is None:
        return "needs_improvement"
    if architecture.get("status") != "ok":
        return "blocked"
    if spec is None:
        return "blocked"
    return "ok" if spec.get("status") == "ok" else "blocked"


def _next_action(
    architecture: dict[str, Any],
    *,
    semantic_gap: bool = False,
    developer_request: dict[str, Any] | None = None,
) -> str:
    if architecture.get("status") == "needs_clarification":
        return "ask_user_clarification"
    if semantic_gap:
        if developer_request is not None:
            return "record_developer_improvement_request"
        return "request_l45_semantic_hypothesis"
    if architecture.get("status") != "ok":
        return "stop_blocked"
    return "handoff_to_spec_writer"


def _summary(artifact: dict[str, Any] | None, path: str | None) -> dict[str, Any] | None:
    if artifact is None:
        return None
    summary = {
        "artifact_type": artifact.get("artifact_type"),
        "role": artifact.get("role"),
        "status": artifact.get("status"),
        "path": path,
    }
    if artifact.get("artifact_type") == "ProductArchitectureRecord":
        summary["pattern_id"] = artifact.get("pattern_id")
        summary["component_ids"] = [str(row.get("id")) for row in artifact.get("components", []) if isinstance(row, dict)]
    if artifact.get("artifact_type") == "ProductTechnicalSpec":
        summary["primary_contract"] = dict(artifact.get("primary_contract") or {}).get("name")
    return summary


def _is_generic_greenfield_pattern(architecture: dict[str, Any]) -> bool:
    return str(architecture.get("pattern_id") or "") == "generic_product"


def _greenfield_semantic_gap_decision(*, prompt: str, architecture: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "CognitiveControlDecision",
        "layer": "L4.0",
        "mode": "prompt_to_product",
        "status": "blocked",
        "prompt": prompt,
        "role_transition": {
            "from_role": "architect",
            "to_role": "spec_writer",
            "next_action": "request_l45_semantic_hypothesis",
            "reason": "greenfield_pattern_missing",
        },
        "semantic_escalation": {
            "l4_5_required": True,
            "reasons": ["no_supported_package_template"],
        },
        "evidence_refs": [
            "ProductArchitectureRecord.pattern_id=generic_product",
            "ProductArchitectureRecord.status=ok",
        ],
        "forbidden_actions": [
            "handoff_to_spec_writer",
            "build_generic_spec_as_success",
            "edit_runtime_templates",
            "mutate_registry",
        ],
        "fallback_policy": "request_l45_semantic_hypothesis_then_developer_improvement_request",
    }


def _architecture_gap_context(architecture: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": architecture.get("artifact_type"),
        "status": architecture.get("status"),
        "pattern_id": architecture.get("pattern_id"),
        "system_type": architecture.get("system_type"),
        "open_question_policy": dict(architecture.get("open_question_policy") or {}),
        "forbidden_actions_enforced": list(architecture.get("forbidden_actions_enforced") or []),
    }
