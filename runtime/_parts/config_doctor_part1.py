from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from runtime.architecture_decision_policy import load_architecture_decision_policy
from runtime.architecture_synthesis_policy import load_architecture_synthesis_policy
from runtime.contract_transform_contract_profiles import load_contract_transform_contract_profiles
from runtime.contract_transform_operators import load_contract_transform_operators
from runtime.dependency_extraction_policy import load_dependency_extraction_policy
from runtime.executable_acceptance_policy import load_executable_acceptance_policy
from runtime.executor_solution_patterns import load_executor_solution_patterns
from runtime.foundation_semantic_quality_policy import load_foundation_semantic_quality_policy
from runtime.interface_contracts import load_interface_contracts
from runtime.greenfield_architecture_patterns import load_greenfield_architecture_patterns
from runtime.l4_decision_table import load_l4_decision_rules
from runtime.local_inference import load_llm_profiles
from runtime.knowledge_import import load_pypi_archetype_rules
from runtime.operation_recipe_rules import load_operation_recipe_rules
from runtime.patch_synthesis_policy import load_patch_synthesis_policy
from runtime.programmer_executor_playbooks import load_programmer_executor_playbooks
from runtime.project_evolution_policy import load_project_evolution_policy
from runtime.project_probe_env_policy import load_project_probe_env_policy
from runtime.prompt_intake_rules import load_prompt_intake_rules
from runtime.role_promotion_policy import load_role_promotion_policy
from runtime.role_directory import load_role_directory
from runtime.role_workflow_handler_registry import workflow_handler_registration_errors
from runtime.runtime_interpreter_policy import load_runtime_interpreter_policy
from runtime.sandbox_programmer_profiles import load_sandbox_programmer_profiles
from runtime.sandbox_release_policy import load_sandbox_release_policy
from runtime.semantic_target_profiles import load_semantic_target_profiles
from runtime.semantic_resolution_rules import load_semantic_resolution_rules
from runtime.source_target_policy import load_role_source_policy
from runtime.system_knowledge_ir_backlog import load_ir_backlog_policy
from runtime.stage2_template_routes import load_stage2_template_routes
from runtime.target_quality_policy import load_target_quality_policy
from runtime.technical_spec_policy import load_technical_spec_policy
from runtime.web_extraction_profiles import load_web_extraction_profiles

ROOT = Path(__file__).resolve().parents[2]

@dataclass
class _Check:
    code: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "status": "failed" if self.errors else "passed",
            "errors": self.errors,
            "warnings": self.warnings,
        }

def run_config_doctor(root: Path | None = None) -> dict[str, Any]:
    base = (root or ROOT).resolve()
    checks = [
        _load_check(
            "load_external_config_catalogs",
            lambda: _load_catalogs(base),
        ),
    ]
    catalogs = _load_catalogs(base)
    checks.extend(
        [
            _check_role_directory(catalogs),
            _check_stage2_routes(catalogs, base),
            _check_semantic_resolution(catalogs),
            _check_semantic_target_profiles(catalogs),
            _check_web_extraction_profiles(catalogs),
            _check_operation_recipes(catalogs),
            _check_sandbox_programmer(catalogs),
            _check_sandbox_attempt_policy(catalogs, base),
            _check_l4_decision_rules(catalogs),
            _check_architecture_synthesis_policy(catalogs),
            _check_foundation_semantic_quality_policy(catalogs),
            _check_executable_acceptance_policy(catalogs),
            _check_contract_transform_operators(catalogs),
            _check_contract_transform_contract_profiles(catalogs),
            _check_dependency_extraction_policy(catalogs),
            _check_patch_synthesis_policy(catalogs),
            _check_programmer_executor_playbooks(catalogs),
            _check_executor_solution_patterns(catalogs),
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
    )
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

def _load_check(code: str, fn: Callable[[], Any]) -> _Check:
    check = _Check(code)
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - doctor reports config failures.
        check.errors.append(f"{type(exc).__name__}:{exc}")
    return check

def _load_catalogs(root: Path) -> dict[str, Any]:
    return {
        "role_directory": load_role_directory(str(root / "config" / "role_directory.json")),
        "runtime_interpreter_policy": load_runtime_interpreter_policy(str(root / "config" / "runtime_interpreter_policy.json")),
        "prompt_intake_rules": load_prompt_intake_rules(str(root / "config" / "prompt_intake_rules.json")),
        "semantic_resolution_rules": load_semantic_resolution_rules(str(root / "config" / "semantic_resolution_rules.json")),
        "semantic_target_profiles": load_semantic_target_profiles(str(root / "config" / "semantic_target_profiles.json")),
        "stage2_template_routes": load_stage2_template_routes(str(root / "config" / "stage2_template_routes.json")),
        "web_extraction_profiles": load_web_extraction_profiles(str(root / "config" / "web_extraction_profiles.json")),
        "operation_recipe_rules": load_operation_recipe_rules(str(root / "config" / "operation_recipe_rules.json")),
        "sandbox_programmer_profiles": load_sandbox_programmer_profiles(str(root / "config" / "sandbox_programmer_profiles.json")),
        "sandbox_release_policy": load_sandbox_release_policy(str(root / "config" / "sandbox_release_policy.json")),
        "l4_decision_rules": load_l4_decision_rules(str(root / "config" / "l4_decision_rules.json")),
        "interface_contracts": load_interface_contracts(root),
        "greenfield_architecture_patterns": load_greenfield_architecture_patterns(str(root / "config" / "greenfield_architecture_patterns.json")),
        "target_quality_policy": load_target_quality_policy(str(root / "config" / "target_quality_policy.json")),
        "technical_spec_policy": load_technical_spec_policy(str(root / "config" / "technical_spec_policy.json")),
        "architecture_decision_policy": load_architecture_decision_policy(str(root / "config" / "architecture_decision_policy.json")),
        "architecture_synthesis_policy": load_architecture_synthesis_policy(str(root / "config" / "architecture_synthesis_policy.json")),
        "foundation_semantic_quality_policy": load_foundation_semantic_quality_policy(str(root / "config" / "foundation_semantic_quality_policy.json")),
        "executable_acceptance_policy": load_executable_acceptance_policy(str(root / "config" / "executable_acceptance_policy.json")),
        "contract_transform_operators": load_contract_transform_operators(str(root / "config" / "contract_transform_operators.json")),
        "contract_transform_contract_profiles": load_contract_transform_contract_profiles(str(root / "config" / "contract_transform_contract_profiles.json")),
        "dependency_extraction_policy": load_dependency_extraction_policy(str(root / "config" / "dependency_extraction_policy.json")),
        "patch_synthesis_policy": load_patch_synthesis_policy(str(root / "config" / "patch_synthesis_policy.json")),
        "programmer_executor_playbooks": load_programmer_executor_playbooks(str(root / "config" / "programmer_executor_playbooks.json")),
        "executor_solution_patterns": load_executor_solution_patterns(str(root / "config" / "executor_solution_patterns.json")),
        "project_evolution_policy": load_project_evolution_policy(str(root / "config" / "project_evolution_policy.json")),
        "project_probe_env_policy": load_project_probe_env_policy(str(root / "config" / "project_probe_env_policy.json")),
        "pypi_archetype_rules": load_pypi_archetype_rules(str(root / "knowledge" / "architecture_patterns" / "pypi_archetype_inference.json")),
        "ir_backlog_policy": load_ir_backlog_policy(str(root / "config" / "system_knowledge_ir_backlog_policy.json")),
        "role_promotion_policy": load_role_promotion_policy(str(root / "config" / "role_promotion_policy.json")),
        "llm_profiles": load_llm_profiles(str(root / "config" / "llm_profiles.json")),
        "role_source_policy": load_role_source_policy(str(root / "config" / "role_source_policy.json")),
        "sandbox_operations": _read_json(root / "registry" / "sandbox_programmer_operations.json"),
        "sandbox_compositions": _read_json(root / "registry" / "sandbox_programmer_compositions.json"),
        "sandbox_attempt_policy": _read_json(root / "registry" / "sandbox_attempt_policy.json"),
        "local_automation_cases": _read_json(root / "registry" / "local_automation_mvp_cases.json"),
    }

def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def _check_role_directory(catalogs: dict[str, Any]) -> _Check:
    check = _Check("role_directory_pipeline_integrity")
    directory = catalogs["role_directory"]
    roles = dict(directory.get("roles") or {})
    outputs: set[str] = set()
    stages = list(dict(directory.get("workflow") or {}).get("stages") or [])
    check.errors.extend(workflow_handler_registration_errors(stages))
    for step in directory.get("pipeline", []):
        role_id = str(dict(step).get("role_id") or "")
        role = dict(roles.get(role_id) or {})
        if role_id not in roles:
            check.errors.append(f"unknown_pipeline_role:{role_id}")
            continue
        output_key = str(dict(step).get("output_key") or "")
        if output_key in outputs:
            check.errors.append(f"duplicate_pipeline_output_key:{output_key}")
        outputs.add(output_key)
        builder = dict(role.get("artifact_builder") or {})
        if not builder.get("callable") or not builder.get("artifact_type"):
            check.errors.append(f"missing_builder_contract:{role_id}")
    return check

def _check_stage2_routes(catalogs: dict[str, Any], root: Path) -> _Check:
    check = _Check("stage2_template_routes_integrity")
    routes = catalogs["stage2_template_routes"]
    known = {str(item) for item in routes.get("known_templates", [])}
    routed = {str(dict(row).get("case") or "") for row in routes.get("routes", [])}
    for case_name in sorted(routed - known):
        check.errors.append(f"route_unknown_case:{case_name}")
    for case_name in sorted(known - routed):
        check.warnings.append(f"known_template_without_route:{case_name}")
    curriculum = root / "curricula" / "programmer_prompt_stage2"
    for case_name in sorted(known):
        if not (curriculum / case_name / "teacher_reference.json").is_file():
            check.warnings.append(f"template_without_teacher_reference:{case_name}")
    return check

def _check_semantic_resolution(catalogs: dict[str, Any]) -> _Check:
    check = _Check("semantic_resolution_references")
    known = {str(item) for item in catalogs["stage2_template_routes"].get("known_templates", [])}
    rules = catalogs["semantic_resolution_rules"]
    for row in rules.get("existing_resolution_rules", []):
        required = str(dict(row).get("required_template") or "")
        if required not in known:
            check.errors.append(f"semantic_rule_unknown_template:{required}")
    return check

def _check_semantic_target_profiles(catalogs: dict[str, Any]) -> _Check:
    check = _Check("semantic_target_profiles_integrity")
    seen = set()
    for row in catalogs["semantic_target_profiles"].get("profiles", []):
        profile = dict(row)
        profile_id = str(profile.get("id") or "")
        if profile_id in seen:
            check.errors.append(f"duplicate_semantic_target_profile:{profile_id}")
        seen.add(profile_id)
        symbol_fields = ("symbols", "symbol_prefixes", "symbol_contains_any", "symbol_contains_all")
        if not any(profile.get(field_name) for field_name in symbol_fields):
            check.errors.append(f"semantic_target_profile_without_symbol_matcher:{profile_id}")
        for excluded in profile.get("exclude_if_profile_ids", []):
            if str(excluded) not in seen and not any(
                str(candidate.get("id") or "") == str(excluded)
                for candidate in catalogs["semantic_target_profiles"].get("profiles", [])
            ):
                check.errors.append(f"semantic_target_profile_unknown_exclusion:{profile_id}:{excluded}")
        if profile.get("contract_family"):
            required = ["input_contract", "output_contract", "side_effect_policy", "validation_gates", "failure_modes"]
            for field_name in required:
                ok = isinstance(profile.get(field_name), dict) if field_name == "input_contract" else bool(profile.get(field_name))
                if not ok:
                    check.errors.append(f"semantic_target_contract_missing_{field_name}:{profile_id}")
        if profile.get("score_bonus") and profile.get("score_penalty"):
            check.warnings.append(f"semantic_target_profile_has_bonus_and_penalty:{profile_id}")
    return check

def _check_web_extraction_profiles(catalogs: dict[str, Any]) -> _Check:
    check = _Check("web_extraction_profiles_integrity")
    seen = set()
    for row in catalogs["web_extraction_profiles"].get("profiles", []):
        host = str(dict(row).get("host") or "")
        kind = str(dict(row).get("target_kind") or "")
        key = (host, kind)
        if key in seen:
            check.errors.append(f"duplicate_web_extraction_profile:{kind}:{host}")
        seen.add(key)
        if not host or "." not in host:
            check.errors.append(f"invalid_web_extraction_host:{host}")
        if kind not in {"news"}:
            check.warnings.append(f"unknown_web_extraction_target_kind:{kind}:{host}")
    return check

def _check_operation_recipes(catalogs: dict[str, Any]) -> _Check:
    check = _Check("operation_recipe_references")
    rules = catalogs["operation_recipe_rules"]
    contracts = set(catalogs["interface_contracts"])
    profiles = set(dict(catalogs["sandbox_programmer_profiles"].get("profiles") or {}))
    for contract in rules.get("allowed_interface_contracts", []):
        if str(contract) not in contracts:
            check.errors.append(f"unknown_interface_contract:{contract}")
    for contract, profile in dict(rules.get("contract_profiles") or {}).items():
        if str(contract) not in contracts:
            check.errors.append(f"contract_profile_unknown_contract:{contract}")
        if str(profile) not in profiles:
            check.errors.append(f"contract_profile_unknown_profile:{profile}")
    for row in rules.get("text_interface_resolution", []):
        contract = str(dict(row).get("interface_contract") or "")
        if contract not in contracts:
            check.errors.append(f"text_resolution_unknown_contract:{contract}")
    return check

def _check_sandbox_programmer(catalogs: dict[str, Any]) -> _Check:
    check = _Check("sandbox_programmer_registry_integrity")
    profiles = set(dict(catalogs["sandbox_programmer_profiles"].get("profiles") or {}))
    operations = {str(row.get("id") or ""): dict(row) for row in catalogs["sandbox_operations"].get("operations", [])}
    for operation_id, row in sorted(operations.items()):
        profile = str(row.get("profile") or "")
        if profile not in profiles:
            check.errors.append(f"operation_unknown_profile:{operation_id}:{profile}")
    seen = set()
    for operation_id in operations:
        if operation_id in seen:
            check.errors.append(f"duplicate_operation_id:{operation_id}")
        seen.add(operation_id)
    for composition in catalogs["sandbox_compositions"].get("compositions", []):
        for step in dict(composition).get("steps", []):
            operation_id = str(dict(step).get("operation") or "")
            if operation_id not in operations:
                check.errors.append(f"composition_unknown_operation:{dict(composition).get('id')}:{operation_id}")
    return check

def _check_sandbox_attempt_policy(catalogs: dict[str, Any], root: Path) -> _Check:
    check = _Check("sandbox_attempt_policy_references")
    policy = catalogs["sandbox_attempt_policy"]
    known = {str(item) for item in catalogs["stage2_template_routes"].get("known_templates", [])}
    curriculum = root / "curricula" / "programmer_prompt_stage2"
    for kind, entry in dict(policy.get("allowed_attempt_kinds") or {}).items():
        for case_name in dict(entry).get("cases", []):
            case = str(case_name)
            if case not in known:
                check.errors.append(f"attempt_kind_unknown_case:{kind}:{case}")
            if dict(entry).get("requires_curriculum_reference") and not (curriculum / case / "teacher_reference.json").is_file():
                check.errors.append(f"attempt_kind_missing_teacher_reference:{kind}:{case}")
    return check

def _check_l4_decision_rules(catalogs: dict[str, Any]) -> _Check:
    check = _Check("l4_decision_rule_integrity")
    seen = set()
    for rule in catalogs["l4_decision_rules"].get("rules", []):
        rule_id = str(dict(rule).get("rule_id") or "")
        if rule_id in seen:
            check.errors.append(f"duplicate_l4_rule_id:{rule_id}")
        seen.add(rule_id)
        if not dict(rule).get("next_action"):
            check.errors.append(f"l4_rule_without_next_action:{rule_id}")
    return check

def _check_architecture_synthesis_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("architecture_synthesis_policy_integrity")
    policy = dict(catalogs["architecture_synthesis_policy"])
    if policy.get("status") != "active":
        check.errors.append("architecture_synthesis_policy_inactive")
    if not policy.get("fallback_target_shape"):
        check.errors.append("architecture_synthesis_policy_missing:fallback_target_shape")
    first_slice = dict(policy.get("default_first_slice") or {})
    for field_name in ("name", "goal", "target_task_types", "steps"):
        if not first_slice.get(field_name):
            check.errors.append(f"architecture_synthesis_policy_missing:default_first_slice.{field_name}")
    bottlenecks = dict(policy.get("bottlenecks") or {})
    if not bottlenecks.get("rules"):
        check.errors.append("architecture_synthesis_policy_missing:bottlenecks.rules")
    for row in list(bottlenecks.get("rules") or []):
        rule = dict(row)
        for field_name in ("kind", "source", "reason", "severity"):
            if not rule.get(field_name):
                check.errors.append(f"architecture_synthesis_bottleneck_rule_missing:{field_name}")
    if not dict(policy.get("task_focus") or {}).get("preferred_order"):
        check.errors.append("architecture_synthesis_policy_missing:task_focus.preferred_order")
    return check

def _check_foundation_semantic_quality_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("foundation_semantic_quality_policy_integrity")
    policy = dict(catalogs["foundation_semantic_quality_policy"])
    if not isinstance(policy.get("status_threshold"), (int, float)):
        check.errors.append("foundation_semantic_quality_policy_missing:status_threshold")
    for section_name in (
        "specific_text",
        "domain_profile",
        "project_analyzer",
        "architect",
        "spec_writer",
        "source_reference",
        "side_effect_policy",
    ):
        if not isinstance(policy.get(section_name), dict) or not policy.get(section_name):
            check.errors.append(f"foundation_semantic_quality_policy_missing:{section_name}")
    if not dict(policy.get("specific_text") or {}).get("generic_phrases"):
        check.errors.append("foundation_semantic_quality_policy_missing:specific_text.generic_phrases")
    if not dict(policy.get("spec_writer") or {}).get("negative_case_tokens"):
        check.errors.append("foundation_semantic_quality_policy_missing:spec_writer.negative_case_tokens")
    return check
