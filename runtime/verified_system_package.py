"""Stage 2 Prompt -> Verified System Package runner."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cognitive_control_plane import run_prompt_product_control_plane
from .fallback_autonomy_loop import run_fallback_autonomy_loop
from .generic_file_conversion_recipe import build_conversion_recipe, is_file_conversion_prompt
from .generated_package_evaluation import evaluate_generated_package
from .knowledge_admission import build_kb_candidate, write_kb_candidate
from .greenfield_generic_file_converter_template import expected_artifacts as generic_converter_expected_artifacts
from .l4_semantic_validation import validate_l45_semantic_proposal
from .llm_sandbox_implementation import run_llm_sandbox_implementation
from .programmer_project_review import run_programmer_project_review
from .prompt_adequacy import evaluate_prompt_adequacy
from .rule_trace import build_rule_trace
from .sandbox_programmer_admission import review_sandbox_programmer_result
from .stage2_template_routes import (
    known_stage2_templates,
    looks_like_format_continuation,
    requested_output_formats,
    select_stage2_case,
)
from .semantic_evidence_pack import build_semantic_evidence_pack
from .semantic_reasoner import (
    build_developer_improvement_request,
    build_semantic_hypothesis_request,
    build_stage2_template_backlog_item,
    build_successful_resolution_candidate,
    run_semantic_reasoner,
)
from .stage2_debug_loop import run_stage2_debug_loop


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
    return {
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


def _sandbox_success_candidate(result: dict[str, Any], admission: dict[str, Any]) -> dict[str, Any]:
    operation = dict(dict(result.get("implementation_plan", {})).get("operation", {}))
    operation_id = str(operation.get("operation") or "unknown_operation")
    return build_kb_candidate(
        record_type="successful_resolution_candidate",
        proposed_record={
            "record_type": "successful_resolution_candidate",
            "rule_id": f"sandbox_programmer_{operation_id}",
            "label": f"Sandbox programmer can build {operation_id} CLI",
            "role_scope": ["implementer", "tester", "reviewer"],
            "prompt_markers": list(operation.get("evidence", [])),
            "operation": operation,
            "candidate_origin": "LLMSandboxImplementationResult",
            "auto_promote": False,
        },
        source_cases=[
            {
                "status": "verified",
                "prompt": result.get("prompt"),
                "operation": operation_id,
                "sandbox_status": result.get("status"),
                "admission_status": admission.get("status"),
            }
        ],
        teacher_reference="sandbox_programmer_admission",
    )


def _llm_sandbox_gate(result: dict[str, Any], admission: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "project_dir_present": bool(result.get("project_dir")),
        "verification_passed": dict(result.get("verification", {})).get("status") == "passed",
        "tester_reviewer_admitted": admission.get("release_candidate") is True,
        "source_tree_unchanged": result.get("source_code_changes") is False,
        "registry_unchanged": result.get("registry_changes") is False,
        "kb_not_promoted": result.get("promotion_allowed") is False,
    }
    failed = [name for name, ok in checks.items() if not ok]
    return {
        "artifact_type": "ProgrammerSandboxGate",
        "status": "passed" if not failed else "failed",
        "checks": checks,
        "failed_checks": failed,
        "policy": {
            "sandbox_only": True,
            "source_apply_requires_human_approval": True,
            "release_requires_project_scoped_verification": True,
            "kb_promotion_forbidden": True,
        },
    }


def _select_case(prompt: str) -> str | None:
    return select_stage2_case(prompt)


def _load_stage2_output_context(output_dir: Path | None) -> dict[str, Any]:
    if output_dir is None:
        return {}
    manifest_path = output_dir / "scaffold_manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        "artifact_type": str(manifest.get("artifact_type") or ""),
        "case": str(manifest.get("case") or ""),
        "project_dir": str(manifest.get("project_dir") or output_dir.as_posix()),
        "previous_prompt": str(manifest.get("prompt") or ""),
    }


def _effective_prompt(prompt: str, continuation_context: dict[str, Any]) -> str:
    if not continuation_context or not looks_like_format_continuation(prompt):
        return _expand_known_short_prompt(prompt)
    case_name = str(continuation_context.get("case") or "")
    if case_name == "image_table_to_excel_cli":
        formats = requested_output_formats(prompt)
        format_text = ", ".join(formats) if formats else "requested additional formats"
        return (
            "Доработай проект 12: CLI должна читать изображение табличной сметы и уметь выводить результат "
            f"в существующие форматы и дополнительно в {format_text}. "
            "Тесты без сети через injectable OCR/text backend."
        )
    return prompt


def _expand_known_short_prompt(prompt: str) -> str:
    if is_file_conversion_prompt(prompt):
        recipe = build_conversion_recipe(prompt)
        if recipe is None:
            return prompt
        return (
            "Напиши локальную CLI .py утилиту без обязательных внешних зависимостей: "
            f"вход - путь к файлу {recipe.source_ext}, выход - файл {recipe.target_ext} с тем же базовым именем "
            "или указанным output path. Реальная конвертация должна быть отделена adapter boundary; default tests "
            "работают без внешних библиотек и сети через deterministic fixture adapter. CLI должен явно обрабатывать "
            "отсутствующий файл, неподдержанное входное/выходное расширение и ошибку adapter backend. "
            "Нужны README и pytest."
        )
    return prompt


def _has_legacy_xls_token(lower: str) -> bool:
    return re.search(r"(?<!x)\.xls(?!x)\b|\blegacy\s+\.xls\b", lower) is not None


def _case_from_continuation(prompt: str, continuation_context: dict[str, Any]) -> str | None:
    if not continuation_context or not looks_like_format_continuation(prompt):
        return None
    case_name = str(continuation_context.get("case") or "")
    return case_name or None


def _load_reference(curriculum_dir: Path, case_name: str) -> dict[str, Any]:
    return json.loads((curriculum_dir / case_name / "teacher_reference.json").read_text(encoding="utf-8"))


def _synthetic_reference(prompt: str, case_name: str | None) -> dict[str, Any] | None:
    if case_name != "generic_file_converter_cli":
        return None
    recipe = build_conversion_recipe(prompt)
    if recipe is None:
        return None
    return {
        "artifact_type": "TeacherReference",
        "case": case_name,
        "teacher_reference_not_ground_truth": True,
        "prompt": prompt,
        "expected_artifacts": generic_converter_expected_artifacts(prompt),
        "acceptance_criteria": [
            "conversion recipe captures source and target formats",
            "library binding recipe proposes bounded adapter candidates",
            "adapter implementation plan selects implemented stdlib backend or fallback",
            "CLI writes target output through adapter boundary",
            "missing or unsupported inputs are rejected with controlled errors",
            "default tests run without real conversion dependencies or network",
            "all tests run from generated project root",
        ],
        "recipe": recipe.to_dict(),
    }


def _documentation_pack(programmer: dict[str, Any], tester: dict[str, Any], system_type: str) -> dict[str, Any]:
    project_dir = str(programmer.get("project_dir") or "")
    run_instructions = [
        "python -m compileall -b .",
        "python -m pytest tests -q",
    ]
    if system_type == "fastapi_service":
        package = _fastapi_package(programmer)
        run_instructions.append(f"uvicorn {package}.app:app --app-dir src")
    else:
        run_instructions.append("run package CLI through generated module main() or python -m package.cli when packaged")
    return {
        "readme": f"{project_dir}/README.md" if project_dir else None,
        "run_instructions": run_instructions,
        "verification_summary": {
            "tester_recommendation": tester.get("recommendation"),
            "missing_acceptance": dict(tester.get("coverage", {})).get("missing_acceptance", []),
        },
    }


def _fastapi_package(programmer: dict[str, Any]) -> str:
    files = [str(row.get("path") or "") for row in programmer.get("files", [])]
    for path in files:
        if path.startswith("src/") and path.endswith("/app.py"):
            return path.split("/")[1]
    return "package"


def _programmer_sandbox_gate(programmer: dict[str, Any], tester: dict[str, Any]) -> dict[str, Any]:
    verification = dict(programmer.get("verification", {}))
    checks = {
        "project_dir_present": bool(programmer.get("project_dir")),
        "verification_passed": verification.get("status") == "passed",
        "tester_approved": tester.get("recommendation") in {"approve", "approve_with_risks"},
        "source_tree_unchanged": programmer.get("source_code_changes", False) is False,
        "registry_unchanged": programmer.get("registry_changes", False) is False,
    }
    failed = [name for name, ok in checks.items() if not ok]
    return {
        "artifact_type": "ProgrammerSandboxGate",
        "status": "passed" if not failed else "failed",
        "checks": checks,
        "failed_checks": failed,
        "policy": {
            "sandbox_only": True,
            "source_apply_requires_human_approval": True,
            "release_requires_project_scoped_verification": True,
        },
    }


def _tester_limitations(tester: dict[str, Any]) -> list[str]:
    risks = tester.get("risk_assessment", [])
    return [str(item.get("risk")) for item in risks if item.get("severity") in {"medium", "high"}]


def _release_decision(tester: dict[str, Any]) -> dict[str, str]:
    recommendation = tester.get("recommendation")
    if recommendation == "approve":
        return {"decision": "release_ready", "reason": "tester approved generated package"}
    if recommendation == "approve_with_risks":
        return {"decision": "release_ready_with_risks", "reason": "tester approved with documented risks"}
    return {"decision": "blocked", "reason": "tester requested rework or review did not pass"}


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "verified_system_packages"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"verified_system_package_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
