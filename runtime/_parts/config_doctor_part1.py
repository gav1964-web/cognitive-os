"""Core orchestration for the split config doctor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plugins.project_map_report.src.language_scope import load_language_scope_policy
from runtime._parts.config_doctor_catalogs import _load_catalogs, _read_json
from runtime._parts.config_doctor_common import ROOT, _Check, _load_check
from runtime._parts.config_doctor_core_checks import (
    _check_architecture_synthesis_policy,
    _check_foundation_semantic_quality_policy,
    _check_l4_decision_rules,
    _check_operation_recipes,
    _check_pilot_blind_corpus_policy,
    _check_pilot_profile,
    _check_programmer_task_tree_policy,
    _check_role_directory,
    _check_role_project_type_policy,
    _check_sandbox_attempt_policy,
    _check_sandbox_programmer,
    _check_semantic_resolution,
    _check_semantic_target_profiles,
    _check_stage2_routes,
    _check_web_extraction_profiles,
)
from runtime._parts.config_doctor_knowledge_checks import (
    _check_exception_pickle_reconstruction_knowledge,
    _check_llm_profiles,
    _check_project_development_boundary_knowledge,
    _check_project_evolution_policy,
    _check_project_native_cli_repair_knowledge,
    _check_role_promotion_policy,
    _check_role_source_policy,
)
from runtime._parts.config_doctor_policy_checks import (
    _check_contract_transform_contract_profiles,
    _check_contract_transform_operators,
    _check_executable_acceptance_policy,
    _check_executor_solution_patterns,
    _check_patch_synthesis_policy,
    _check_programmer_executor_playbooks,
    _check_self_improvement_contract_families,
    _check_target_quality_policy,
)
from runtime._parts.config_doctor_project_policy import _check_project_development_policy
from runtime.first_slice_viability import load_first_slice_viability
from runtime.function_invocation_patterns import load_function_invocation_patterns
from runtime.source_line_limit_audit import run_source_line_limit_audit
from runtime.spec_writer_ranking_kb import assert_no_knowledge_leakage, load_spec_writer_ranking_kb


def run_config_doctor(root: Path | None = None) -> dict[str, Any]:
    base = (root or ROOT).resolve()
    checks = [
        _load_check("load_external_config_catalogs", lambda: _load_catalogs(base)),
        _load_check(
            "first_slice_viability_kb_integrity",
            lambda: load_first_slice_viability(
                str(base / "knowledge" / "architecture_patterns" / "first_slice_viability.json")
            ),
        ),
        _load_check(
            "spec_writer_ranking_kb_integrity",
            lambda: load_spec_writer_ranking_kb(
                str(base / "knowledge" / "role_knowledge" / "spec_writer_ranking.json")
            ),
        ),
        _load_check("spec_writer_knowledge_leakage", lambda: assert_no_knowledge_leakage(base)),
        _load_check(
            "language_scope_kb_integrity",
            lambda: load_language_scope_policy(
                str(base / "knowledge" / "architecture_patterns" / "language_scope.json")
            ),
        ),
        _load_check(
            "function_invocation_patterns_kb_integrity",
            lambda: load_function_invocation_patterns(
                base / "knowledge" / "role_knowledge" / "function_invocation_patterns.json"
            ),
        ),
        _load_check("source_line_limit_gate", lambda: _assert_source_line_limit(base)),
    ]
    catalogs = _load_catalogs(base)
    checks.extend(_catalog_checks(catalogs, base))
    rows = [check.to_dict() for check in checks]
    failed = [row for row in rows if row["status"] == "failed"]
    return {
        "artifact_type": "ConfigDoctorReport",
        "status": "failed" if failed else "ok",
        "root": base.as_posix(),
        "summary": {
            "passed": len(rows) - len(failed),
            "failed": len(failed),
            "warnings": sum(len(row["warnings"]) for row in rows),
        },
        "checks": rows,
    }


def _assert_source_line_limit(base: Path) -> None:
    report = run_source_line_limit_audit(root=base)
    if report["status"] != "passed":
        count = int(report.get("violation_count") or 0)
        top = [
            f"{row.get('path')}:{row.get('line_count')}"
            for row in list(report.get("top_violations") or [])[:5]
        ]
        raise ValueError(f"{count} Python source files exceed line limit: {', '.join(top)}")


def _catalog_checks(catalogs: dict[str, Any], base: Path) -> list[_Check]:
    return [
        _check_role_directory(catalogs),
        _check_stage2_routes(catalogs, base),
        _check_semantic_resolution(catalogs),
        _check_semantic_target_profiles(catalogs),
        _check_self_improvement_contract_families(catalogs),
        _check_web_extraction_profiles(catalogs),
        _check_operation_recipes(catalogs),
        _check_sandbox_programmer(catalogs),
        _check_sandbox_attempt_policy(catalogs, base),
        _check_l4_decision_rules(catalogs),
        _check_architecture_synthesis_policy(catalogs),
        _check_foundation_semantic_quality_policy(catalogs),
        _check_role_project_type_policy(catalogs),
        _check_pilot_profile(catalogs),
        _check_pilot_blind_corpus_policy(catalogs),
        _check_executable_acceptance_policy(catalogs),
        _check_executable_acceptance_source_isolation(catalogs),
        _check_contract_transform_operators(catalogs),
        _check_contract_transform_contract_profiles(catalogs),
        _check_dependency_extraction_policy(catalogs),
        _check_patch_synthesis_policy(catalogs),
        _check_programmer_executor_playbooks(catalogs),
        _check_programmer_task_tree_policy(catalogs),
        _check_executor_solution_patterns(catalogs),
        _check_project_development_policy(catalogs),
        _check_project_development_boundary_knowledge(catalogs),
        _check_exception_pickle_reconstruction_knowledge(catalogs),
        _check_project_native_cli_repair_knowledge(catalogs),
        _check_project_evolution_policy(catalogs),
        _check_project_probe_env_policy(catalogs),
        _check_pypi_archetype_rules(catalogs),
        _check_ir_backlog_policy(catalogs),
        _check_role_promotion_policy(catalogs),
        _check_llm_profiles(catalogs),
        _check_role_source_policy(catalogs),
        _check_target_quality_policy(catalogs),
        _check_technical_spec_policy(catalogs),
        _check_architecture_decision_policy(catalogs),
    ]


from runtime._parts.config_doctor_part3 import (  # noqa: E402
    _check_architecture_decision_policy,
    _check_dependency_extraction_policy,
    _check_executable_acceptance_source_isolation,
    _check_ir_backlog_policy,
    _check_project_probe_env_policy,
    _check_pypi_archetype_rules,
    _check_technical_spec_policy,
)
