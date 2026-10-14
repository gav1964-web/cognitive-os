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
    stage2_artifacts = stage2_expected_artifacts_for_case(str(case_name or ""), prompt)
    if stage2_artifacts:
        return {
            "artifact_type": "TeacherReference",
            "case": case_name,
            "teacher_reference_not_ground_truth": True,
            "prompt": prompt,
            "expected_artifacts": stage2_artifacts,
            "acceptance_criteria": stage2_acceptance_for(str(case_name), {"status": "passed"}),
        }
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
