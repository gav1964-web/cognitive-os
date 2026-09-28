from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from runtime.cognitive_control_plane import run_prompt_product_control_plane
from runtime.fallback_autonomy_loop import run_fallback_autonomy_loop
from runtime.generic_file_conversion_recipe import build_conversion_recipe, is_file_conversion_prompt
from runtime.generated_package_evaluation import evaluate_generated_package
from runtime.generated_product_quality import evaluate_generated_product
from runtime.knowledge_admission import build_kb_candidate, write_kb_candidate
from runtime.greenfield_generic_file_converter_template import expected_artifacts as generic_converter_expected_artifacts
from runtime.greenfield_stage2_templates import acceptance_for as stage2_acceptance_for
from runtime.greenfield_stage2_templates import expected_artifacts_for_case as stage2_expected_artifacts_for_case
from runtime.l4_semantic_validation import validate_l45_semantic_proposal
from runtime.llm_sandbox_implementation import run_llm_sandbox_implementation
from runtime.programmer_project_review import run_programmer_project_review
from runtime.prompt_adequacy import evaluate_prompt_adequacy
from runtime.rule_trace import build_rule_trace
from runtime.sandbox_programmer_admission import review_sandbox_programmer_result
from runtime.stage2_template_routes import (
    known_stage2_templates,
    looks_like_format_continuation,
    requested_output_formats,
    select_stage2_case,
)
from runtime.semantic_evidence_pack import build_semantic_evidence_pack
from runtime.semantic_reasoner import (
    build_developer_improvement_request,
    build_semantic_hypothesis_request,
    build_stage2_template_backlog_item,
    build_successful_resolution_candidate,
    run_semantic_reasoner,
)
from runtime.stage2_debug_loop import run_stage2_debug_loop

def build_verified_system_package(
    *,
    root: Path,
    prompt: str,
    curriculum_dir: Path,
    write: bool = False,
    output_dir: Path | None = None,
    use_l45_model: bool | None = None,
    allow_llm_sandbox_implementation: bool = True,
) -> dict[str, Any]:
    if use_l45_model is None:
        use_l45_model = os.environ.get("COGNITIVE_OS_USE_L45_LLM", "").lower() in {"1", "true", "yes", "on"}
    continuation_context = _load_stage2_output_context(output_dir)
    effective_prompt = _effective_prompt(prompt, continuation_context)
    gate = evaluate_prompt_adequacy(effective_prompt).to_dict()
    case_name = _select_case(effective_prompt) or _case_from_continuation(prompt, continuation_context)
    control_plane = run_prompt_product_control_plane(
        prompt=effective_prompt,
        prompt_adequacy=gate,
        supported_template=case_name,
    )
    if control_plane["role_transition"]["next_action"] != "build_verified_system_package":
        semantic_evidence_pack = build_semantic_evidence_pack(
            control_plane_decision=control_plane,
            prompt=effective_prompt,
            prompt_adequacy=gate,
            supported_templates=[case_name] if case_name else [],
            known_templates=known_stage2_templates(),
            context={"selected_case": case_name, "continuation_context": continuation_context},
        )
        semantic_request = build_semantic_hypothesis_request(
            control_plane_decision=control_plane,
            context={
                "prompt": effective_prompt,
                "raw_prompt": prompt,
                "supported_template": case_name,
                "evidence_pack": semantic_evidence_pack,
                "continuation_context": continuation_context,
            },
        )
        semantic_proposal = (
            run_semantic_reasoner(request=semantic_request, use_model=use_l45_model)
            if semantic_request is not None
            else None
        )
        semantic_validation = (
            validate_l45_semantic_proposal(request=semantic_request, proposal=semantic_proposal)
            if semantic_request is not None and semantic_proposal is not None
            else None
        )
        stage2_template_backlog_item = (
            build_stage2_template_backlog_item(semantic_proposal or {})
            if semantic_validation is not None
            and semantic_validation["accepted_action"] == "record_template_backlog"
            else None
        )
        successful_resolution_candidate = (
            build_successful_resolution_candidate(semantic_proposal or {})
            if semantic_validation is not None
            and semantic_validation["accepted_action"] == "record_successful_resolution_candidate"
            else None
        )
        developer_improvement_request = (
            build_developer_improvement_request(semantic_proposal or {})
            if semantic_validation is not None
            and semantic_validation["accepted_action"] == "record_developer_improvement_request"
            else None
        )
        fallback_loop = run_fallback_autonomy_loop(
            root=root,
            curriculum_dir=curriculum_dir,
            prompt=effective_prompt,
            semantic_proposal=semantic_proposal,
            semantic_validation=semantic_validation,
            write=write,
        )
        if fallback_loop.get("status") == "sandbox_verified":
            review_run = dict(fallback_loop["sandbox_attempt"])
            report = _release_report(prompt, gate, control_plane, review_run, debug_loop=None)
            if semantic_request is not None:
                report["semantic_hypothesis_request"] = semantic_request
            if semantic_evidence_pack is not None:
                report["semantic_evidence_pack"] = semantic_evidence_pack
            if semantic_proposal is not None:
                report["semantic_hypothesis_proposal"] = semantic_proposal
            if semantic_validation is not None:
                report["l4_semantic_validation"] = semantic_validation
            report["fallback_autonomy_loop"] = fallback_loop
            if successful_resolution_candidate is not None:
                report["successful_resolution_candidate"] = successful_resolution_candidate
            report["release_decision"] = {
                "decision": "release_ready",
                "reason": "fallback autonomy loop verified an existing route in sandbox",
            }
        else:
            llm_sandbox_implementation = (
                run_llm_sandbox_implementation(
                    root=root,
                    prompt=effective_prompt,
                    write=write,
                    use_model=use_l45_model,
                )
                if allow_llm_sandbox_implementation
                else None
            )
            sandbox_programmer_admission = (
                review_sandbox_programmer_result(llm_sandbox_implementation)
                if llm_sandbox_implementation is not None
                and llm_sandbox_implementation.get("status") == "sandbox_verified"
                else None
            )
            sandbox_success_candidate = (
                _sandbox_success_candidate(llm_sandbox_implementation, sandbox_programmer_admission)
                if sandbox_programmer_admission is not None
                and sandbox_programmer_admission.get("release_candidate") is True
                else None
            )
            if write and sandbox_success_candidate is not None:
                sandbox_success_candidate["candidate_path"] = write_kb_candidate(sandbox_success_candidate, root=root).as_posix()
            report = _blocked_report(
                prompt,
                gate,
                case_name,
                control_plane,
                semantic_request,
                semantic_evidence_pack,
                semantic_proposal,
                semantic_validation,
                stage2_template_backlog_item,
                successful_resolution_candidate,
                developer_improvement_request,
                fallback_loop,
                llm_sandbox_implementation,
                sandbox_programmer_admission,
                sandbox_success_candidate,
            )
    else:
        reference_override = _synthetic_reference(effective_prompt, case_name)
        review_run = run_programmer_project_review(
            root=root,
            curriculum_dir=curriculum_dir,
            case_name=case_name,
            write=write,
            output_dir=output_dir,
            reference_override=reference_override,
        )
        reference = reference_override or _load_reference(curriculum_dir, case_name)
        debug_loop = None
        if review_run.get("status") != "ok":
            debug_loop = run_stage2_debug_loop(review_run=review_run, reference=reference, max_attempts=1)
            review_run = dict(debug_loop["final_review_run"])
        report = _release_report(prompt, gate, control_plane, review_run, debug_loop)
    report["effective_prompt"] = effective_prompt
    if continuation_context:
        report["continuation_context"] = continuation_context
    report["rule_trace"] = build_rule_trace(report)
    if write:
        report["package_report_path"] = _write_report(root, report).as_posix()
    return report

def _release_report(
    prompt: str,
    gate: dict[str, Any],
    control_plane: dict[str, Any],
    review_run: dict[str, Any],
    debug_loop: dict[str, Any] | None,
) -> dict[str, Any]:
    programmer = dict(review_run.get("programmer_artifact", {}))
    tester = dict(review_run.get("tester_review", {}))
    verification = dict(programmer.get("verification", {}))
    decision = _release_decision(tester)
    report = {
        "artifact_type": "VerifiedSystemPackage",
        "stage": "Stage 2",
        "status": "ok" if decision["decision"] in {"release_ready", "release_ready_with_risks"} else "blocked",
        "created_at": _now(),
        "prompt": prompt,
        "prompt_adequacy": gate,
        "cognitive_control_plane": control_plane,
        "system_type": gate.get("system_type"),
        "project_dir": programmer.get("project_dir"),
        "source_code": {
            "files": [row.get("path") for row in programmer.get("files", [])],
            "source_tree_changes": False,
            "registry_changes": False,
        },
        "tests": tester.get("coverage", {}),
        "documentation": _documentation_pack(programmer, tester, str(gate.get("system_type") or "")),
        "verification_report": verification,
        "programmer_sandbox_gate": _programmer_sandbox_gate(programmer, tester),
        "known_limitations": programmer.get("limitations", []) + _tester_limitations(tester),
        "tester_review": tester,
        "debug_loop": debug_loop or {"status": "not_needed", "attempts": []},
        "release_decision": decision,
        "invariants": {
            "direct_user_source_modification": False,
            "human_approval_required_for_source_apply": True,
            "teacher_reference_is_ground_truth": False,
        },
    }
    report["generated_product_quality"] = evaluate_generated_product(report)
    return report

def _blocked_report(
    prompt: str,
    gate: dict[str, Any],
    case_name: str | None,
    control_plane: dict[str, Any],
    semantic_hypothesis_request: dict[str, Any] | None,
    semantic_evidence_pack: dict[str, Any] | None,
    semantic_hypothesis_proposal: dict[str, Any] | None,
    l4_semantic_validation: dict[str, Any] | None,
    stage2_template_backlog_item: dict[str, Any] | None,
    successful_resolution_candidate: dict[str, Any] | None,
    developer_improvement_request: dict[str, Any] | None,
    fallback_autonomy_loop: dict[str, Any] | None = None,
    llm_sandbox_implementation: dict[str, Any] | None = None,
    sandbox_programmer_admission: dict[str, Any] | None = None,
    sandbox_success_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = {
        "artifact_type": "VerifiedSystemPackage",
        "stage": "Stage 2",
        "status": "blocked",
        "created_at": _now(),
        "prompt": prompt,
        "prompt_adequacy": gate,
        "cognitive_control_plane": control_plane,
        "selected_case": case_name,
        "blocker": "prompt is not adequate or no supported package template exists",
        "release_decision": {"decision": "blocked", "reason": control_plane["role_transition"]["reason_code"]},
        "invariants": {
            "direct_user_source_modification": False,
            "human_approval_required_for_source_apply": True,
            "teacher_reference_is_ground_truth": False,
        },
    }
    if semantic_hypothesis_request is not None:
        report["semantic_hypothesis_request"] = semantic_hypothesis_request
    if semantic_evidence_pack is not None:
        report["semantic_evidence_pack"] = semantic_evidence_pack
    if semantic_hypothesis_proposal is not None:
        report["semantic_hypothesis_proposal"] = semantic_hypothesis_proposal
    if l4_semantic_validation is not None:
        report["l4_semantic_validation"] = l4_semantic_validation
    if stage2_template_backlog_item is not None:
        report["stage2_template_backlog_item"] = stage2_template_backlog_item
    if successful_resolution_candidate is not None:
        report["successful_resolution_candidate"] = successful_resolution_candidate
    if developer_improvement_request is not None:
        report["developer_improvement_request"] = developer_improvement_request
    if fallback_autonomy_loop is not None:
        report["fallback_autonomy_loop"] = fallback_autonomy_loop
    if llm_sandbox_implementation is not None:
        report["llm_sandbox_implementation"] = llm_sandbox_implementation
    if sandbox_programmer_admission is not None:
        report["sandbox_programmer_admission"] = sandbox_programmer_admission
        report["release_decision"] = dict(sandbox_programmer_admission.get("release_decision", {}))
        report["programmer_sandbox_gate"] = _llm_sandbox_gate(llm_sandbox_implementation or {}, sandbox_programmer_admission)
        report["project_dir"] = (llm_sandbox_implementation or {}).get("project_dir")
        report["source_code"] = {
            "files": list((llm_sandbox_implementation or {}).get("files", [])),
            "source_tree_changes": False,
            "registry_changes": False,
        }
        report["verification_report"] = dict((llm_sandbox_implementation or {}).get("verification", {}))
        report["tester_review"] = sandbox_programmer_admission
        report["generated_package_evaluation"] = evaluate_generated_package(
            prompt=prompt,
            implementation_result=llm_sandbox_implementation or {},
            admission=sandbox_programmer_admission,
        )
        report["known_limitations"] = list(sandbox_programmer_admission.get("known_limitations", []))
        if sandbox_programmer_admission.get("release_candidate") is True:
            report["status"] = "ok"
            report.pop("blocker", None)
        else:
            report["blocker"] = "sandbox implementation failed tester/reviewer admission"
    if sandbox_success_candidate is not None:
        report["sandbox_successful_resolution_candidate"] = sandbox_success_candidate
    return report
